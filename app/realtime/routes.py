
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import asyncio
import json

from app.core.config import get_settings
from app.realtime.cache import live_cache
from app.realtime.event_bus import bus
from app.realtime.storage import save_event, load_recent_events

router = APIRouter(prefix="/api/v1/realtime", tags=["realtime"])


@router.get("/health")
async def realtime_health() -> Dict[str, Any]:
    settings = get_settings()
    return {
        "ok": True,
        "mode": "ultra_realtime_enterprise",
        "enabled": settings.realtime_enabled,
        "cache_size": live_cache.size(),
        "connected_clients": await bus.client_count(),
        "max_events": settings.realtime_max_events,
    }


@router.get("/snapshot")
async def realtime_snapshot(limit: int = 100) -> Dict[str, Any]:
    memory_events = await bus.snapshot(limit=limit)
    if not memory_events:
        memory_events = load_recent_events(limit=limit)
    return {
        "ok": True,
        "mode": "memory+sqlite",
        "cache_size": live_cache.size(),
        "events": memory_events,
    }


@router.post("/publish")
async def publish_event(payload: Dict[str, Any], background_tasks: BackgroundTasks) -> Dict[str, Any]:
    event_type = str(payload.get("event_type") or "manual")
    data = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
    event = await bus.publish(event_type, data)
    background_tasks.add_task(save_event, event)
    live_cache.set(event_type, data)
    return {"ok": True, "event": event}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await bus.connect(websocket)
    try:
        await websocket.send_text(json.dumps({"event_type": "connected", "payload": {"ok": True}}, ensure_ascii=False))
        while True:
            # Keep connection alive and allow client pings/messages.
            msg = await websocket.receive_text()
            if msg:
                await websocket.send_text(json.dumps({"event_type": "ack", "payload": {"received": True}}, ensure_ascii=False))
    except WebSocketDisconnect:
        await bus.disconnect(websocket)
    except Exception:
        await bus.disconnect(websocket)


@router.get("/sse")
async def sse_stream():
    async def generator():
        last_seen = 0
        while True:
            events = await bus.snapshot(limit=50)
            if len(events) > last_seen:
                for event in events[last_seen:]:
                    yield "data: " + json.dumps(event, ensure_ascii=False, default=str) + "\n\n"
                last_seen = len(events)
            await asyncio.sleep(1.0)
    return StreamingResponse(generator(), media_type="text/event-stream")
