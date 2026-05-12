from __future__ import annotations

import asyncio
import json
import os
import time
from collections import deque
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Awaitable, Callable, Deque, Dict, Iterable, List, Optional


@dataclass
class RuntimeStatus:
    backend: str
    queue_name: str
    enqueued: int
    processed: int
    failed: int
    workers: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class InMemoryQueue:
    def __init__(self):
        self.items: Deque[Dict[str, Any]] = deque()

    async def push(self, item: Dict[str, Any]) -> None:
        self.items.append(item)

    async def pop(self) -> Optional[Dict[str, Any]]:
        if self.items:
            return self.items.popleft()
        return None

    def __len__(self):
        return len(self.items)


class RedisQueue:
    def __init__(self, name: str, url: Optional[str] = None):
        import redis  # type: ignore
        self.name = name
        self.client = redis.Redis.from_url(url or os.getenv('REDIS_URL','redis://localhost:6379/0'), decode_responses=True)

    async def push(self, item: Dict[str, Any]) -> None:
        self.client.rpush(self.name, json.dumps(item, ensure_ascii=False))

    async def pop(self) -> Optional[Dict[str, Any]]:
        raw = self.client.lpop(self.name)
        return json.loads(raw) if raw else None

    def __len__(self):
        return int(self.client.llen(self.name))


class KafkaBus:
    """Optional Kafka producer wrapper. Falls back gracefully when kafka-python is absent."""
    def __init__(self, topic: str, bootstrap: Optional[str] = None):
        from kafka import KafkaProducer  # type: ignore
        self.topic = topic
        self.producer = KafkaProducer(bootstrap_servers=bootstrap or os.getenv('KAFKA_BOOTSTRAP_SERVERS','localhost:9092'), value_serializer=lambda v: json.dumps(v).encode('utf-8'))

    def publish(self, payload: Dict[str, Any]) -> None:
        self.producer.send(self.topic, payload)
        self.producer.flush(timeout=5)


class DistributedRuntime:
    """Async worker runtime with Redis/Kafka optional support.

    It works immediately in local/in-memory mode. When REDIS_URL or Kafka libs
    are installed, the same interface can use real infrastructure.
    """
    def __init__(self, queue_name: str = 'betbot:v8:inference', prefer_redis: bool = True, workers: int = 2, audit_dir: str | Path = 'data/enterprise/runtime'):
        self.queue_name = queue_name
        self.backend = 'memory'
        self.workers = max(1, int(workers))
        self.processed = 0
        self.failed = 0
        self.enqueued = 0
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        if prefer_redis and os.getenv('REDIS_URL'):
            try:
                self.queue = RedisQueue(queue_name)
                self.backend = 'redis'
            except Exception:
                self.queue = InMemoryQueue()
        else:
            self.queue = InMemoryQueue()
        self.kafka = None
        if os.getenv('KAFKA_BOOTSTRAP_SERVERS'):
            try:
                self.kafka = KafkaBus(os.getenv('KAFKA_TOPIC','betbot-v8-events'))
            except Exception:
                self.kafka = None

    async def enqueue(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        job = dict(payload)
        job.setdefault('job_id', f"job_{int(time.time()*1000)}_{self.enqueued}")
        job.setdefault('created_at', time.time())
        await self.queue.push(job)
        self.enqueued += 1
        if self.kafka:
            try: self.kafka.publish({'event': 'job_enqueued', 'job': job})
            except Exception: pass
        return {'status': 'ENQUEUED', 'job_id': job['job_id'], 'backend': self.backend}

    async def run_once(self, handler: Callable[[Dict[str, Any]], Any]) -> Dict[str, Any]:
        job = await self.queue.pop()
        if not job:
            return {'status': 'EMPTY'}
        try:
            result = handler(job)
            if asyncio.iscoroutine(result):
                result = await result
            self.processed += 1
            self._write_result(job, result, ok=True)
            return {'status': 'PROCESSED', 'job_id': job.get('job_id'), 'result': result}
        except Exception as exc:
            self.failed += 1
            self._write_result(job, {'error': str(exc)}, ok=False)
            return {'status': 'FAILED', 'job_id': job.get('job_id'), 'error': str(exc)}

    async def drain(self, handler: Callable[[Dict[str, Any]], Any], limit: int = 100) -> List[Dict[str, Any]]:
        out = []
        for _ in range(max(1, limit)):
            res = await self.run_once(handler)
            out.append(res)
            if res.get('status') == 'EMPTY':
                break
        return out

    def distributed_inference(self, jobs: Iterable[Dict[str, Any]], handler: Callable[[Dict[str, Any]], Any]) -> Dict[str, Any]:
        async def _run():
            for j in jobs:
                await self.enqueue(j)
            return await self.drain(handler, limit=100000)
        results = asyncio.run(_run())
        return {'status': 'DISTRIBUTED_INFERENCE_COMPLETE', 'runtime': self.status(), 'results': results}

    def status(self) -> Dict[str, Any]:
        return RuntimeStatus(self.backend, self.queue_name, self.enqueued, self.processed, self.failed, self.workers).to_dict()

    def _write_result(self, job: Dict[str, Any], result: Any, ok: bool) -> None:
        payload = {'ok': ok, 'job': job, 'result': result, 'ts': time.time()}
        path = self.audit_dir / f"{job.get('job_id','unknown')}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
