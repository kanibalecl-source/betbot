
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_FILE = DATA_DIR / "realtime_events.sqlite3"


def init_realtime_db() -> None:
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS realtime_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_realtime_events_created_at ON realtime_events(created_at)")
        conn.commit()


def save_event(event: Dict[str, Any]) -> None:
    init_realtime_db()
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO realtime_events(event_id,event_type,payload,created_at) VALUES(?,?,?,?)",
            (
                str(event.get("event_id")),
                str(event.get("event_type")),
                json.dumps(event.get("payload", {}), ensure_ascii=False, default=str),
                str(event.get("created_at") or datetime.now(UTC).isoformat()),
            ),
        )
        conn.commit()


def load_recent_events(limit: int = 100) -> List[Dict[str, Any]]:
    init_realtime_db()
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            "SELECT event_id,event_type,payload,created_at FROM realtime_events ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    out = []
    for event_id, event_type, payload, created_at in rows:
        try:
            parsed = json.loads(payload)
        except Exception:
            parsed = {}
        out.append({"event_id": event_id, "event_type": event_type, "payload": parsed, "created_at": created_at})
    return list(reversed(out))
