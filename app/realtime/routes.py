from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict, deque
from typing import Any, Dict

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings
from app.core.security import api_key_matches, require_api_key
from app.realtime.cache import live_cache
from app.realtime.event_bus import bus
from app.realtime.storage import load_recent_events, save_event

router = APIRouter(prefix="/api/v1/realtime", tags=["realtime"])
_publish_windows: dict[str, deque[float]] = defaultdict(deque)
_connection_counts: dict[str, int] = defaultdict(int)
_guard_lock = asyncio.Lock()


class PublishEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    payload: dict[str, Any]

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        encoded = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        if len(encoded) > settings.realtime_max_payload_bytes:
            raise ValueError("payload too large")

        def depth(value: Any, level: int = 0) -> int:
            if level > 8:
                return level
            if isinstance(value, dict):
                return max([level, *(depth(item, level + 1) for item in value.values())])
            if isinstance(value, list):
                return max([level, *(depth(item, level + 1) for item in value)])
            return level

        if depth(payload) > 8:
            raise ValueError("payload nesting too deep")
        return payload


def _client_ip(connection: Request | WebSocket) -> str:
    return connection.client.host if connection.client else "unknown"


async def _enforce_publish_rate(client_ip: str) -> None:
    now = time.monotonic()
    limit = max(1, get_settings().realtime_publish_per_minute)
    async with _guard_lock:
        window = _publish_windows[client_ip]
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
        window.append(now)


@router.get("/health", dependencies=[Depends(require_api_key)])
async def realtime_health() -> Dict[str, Any]:
    settings = get_settings()
    return {
        "ok": True,
        "mode": "authenticated_realtime",
        "enabled": settings.realtime_enabled,
        "cache_size": live_cache.size(),
        "connected_clients": await bus.client_count(),
        "max_events": settings.realtime_max_events,
    }


@router.get("/snapshot", dependencies=[Depends(require_api_key)])
async def realtime_snapshot(limit: int = Query(default=100, ge=1, le=500)) -> Dict[str, Any]:
    memory_events = await bus.snapshot(limit=limit)
    if not memory_events:
        memory_events = load_recent_events(limit=limit)
    return {
        "ok": True,
        "mode": "memory+sqlite",
        "cache_size": live_cache.size(),
        "events": memory_events,
    }


@router.post("/publish", dependencies=[Depends(require_api_key)])
async def publish_event(
    payload: PublishEvent,
    request: Request,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    await _enforce_publish_rate(_client_ip(request))
    event = await bus.publish(payload.event_type, payload.payload)
    background_tasks.add_task(save_event, event)
    live_cache.set(payload.event_type, payload.payload)
    return {"ok": True, "event": event}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    supplied_key = websocket.headers.get("x-api-key") or websocket.query_params.get("token")
    if not api_key_matches(supplied_key):
        await websocket.close(code=1008, reason="Unauthorized")
        return

    client_ip = _client_ip(websocket)
    max_connections = max(1, get_settings().realtime_max_connections_per_ip)
    async with _guard_lock:
        if _connection_counts[client_ip] >= max_connections:
            await websocket.close(code=1013, reason="Connection limit exceeded")
            return
        _connection_counts[client_ip] += 1

    await bus.connect(websocket)
    try:
        await websocket.send_text(json.dumps({"event_type": "connected", "payload": {"ok": True}}))
        while True:
            message = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            if len(message.encode("utf-8")) > 4096:
                await websocket.close(code=1009, reason="Message too large")
                return
            await websocket.send_text(json.dumps({"event_type": "ack", "payload": {"received": True}}))
    except asyncio.TimeoutError:
        await websocket.close(code=1000, reason="Idle timeout")
    except WebSocketDisconnect:
        pass
    finally:
        await bus.disconnect(websocket)
        async with _guard_lock:
            _connection_counts[client_ip] = max(0, _connection_counts[client_ip] - 1)


@router.get("/sse", dependencies=[Depends(require_api_key)])
async def sse_stream(request: Request):
    async def generator():
        last_seen = 0
        heartbeat_at = time.monotonic()
        try:
            while not await request.is_disconnected():
                events = await bus.snapshot(limit=50)
                if len(events) > last_seen:
                    for event in events[last_seen:]:
                        yield "data: " + json.dumps(event, ensure_ascii=False, default=str) + "\n\n"
                    last_seen = len(events)
                if time.monotonic() - heartbeat_at >= 15:
                    yield ": heartbeat\n\n"
                    heartbeat_at = time.monotonic()
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            return

    return StreamingResponse(generator(), media_type="text/event-stream")
