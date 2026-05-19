
from __future__ import annotations

import asyncio
import json
import uuid
from collections import deque
from datetime import datetime, UTC
from typing import Any, Deque, Dict, List, Optional, Set

from fastapi import WebSocket


class RealtimeEventBus:
    """In-memory realtime event bus with WebSocket fanout.

    Redis/Postgres can be plugged in through environment variables later, but this
    module works immediately without external services. It is intentionally safe:
    no loop starts on import, and disconnected sockets are cleaned up.
    """

    def __init__(self, max_events: int = 500):
        self.max_events = max_events
        self.events: Deque[Dict[str, Any]] = deque(maxlen=max_events)
        self.clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.clients.discard(websocket)

    async def publish(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        event = {
            "event_id": uuid.uuid4().hex,
            "event_type": event_type,
            "payload": payload,
            "created_at": datetime.now(UTC).isoformat(),
        }
        async with self._lock:
            self.events.append(event)
            clients = list(self.clients)

        if clients:
            message = json.dumps(event, ensure_ascii=False, default=str)
            stale = []
            for client in clients:
                try:
                    await client.send_text(message)
                except Exception:
                    stale.append(client)
            if stale:
                async with self._lock:
                    for client in stale:
                        self.clients.discard(client)
        return event

    async def snapshot(self, limit: int = 100) -> List[Dict[str, Any]]:
        async with self._lock:
            return list(self.events)[-limit:]

    async def client_count(self) -> int:
        async with self._lock:
            return len(self.clients)


bus = RealtimeEventBus()
