
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from app.realtime.event_bus import bus
from app.realtime.storage import save_event

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
LIVE_FILE = DATA_DIR / "live_matches.csv"
AI_FILE = DATA_DIR / "ai_picks.csv"


def _read_csv(path: Path) -> list[dict[str, Any]]:
    try:
        if path.exists() and path.stat().st_size > 0:
            return pd.read_csv(path).fillna("").to_dict(orient="records")
    except Exception:
        return []
    return []


async def publish_current_state() -> None:
    live = _read_csv(LIVE_FILE)
    ai = _read_csv(AI_FILE)
    event = await bus.publish("state_snapshot", {"live_count": len(live), "ai_count": len(ai), "live": live[:25], "ai": ai[:25]})
    save_event(event)


async def realtime_loop(interval: float = 1.0) -> None:
    while True:
        await publish_current_state()
        await asyncio.sleep(interval)
