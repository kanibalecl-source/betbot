from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
HISTORY_DIR = Path(os.getenv("KANIBAL_HISTORY_DIR", str(DATA_DIR / "history")))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_history_dir() -> Path:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return HISTORY_DIR


def _json_default(value: Any) -> str:
    return str(value)


def _stable_id(stream: str, payload: Dict[str, Any]) -> str:
    raw = json.dumps({"stream": stream, "payload": payload}, ensure_ascii=False, sort_keys=True, default=_json_default)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _envelope(stream: str, payload: Dict[str, Any], source: str = "") -> Dict[str, Any]:
    event = {
        "written_at": now_iso(),
        "stream": str(stream),
        "source": str(source or ""),
        "payload": payload,
    }
    event["event_id"] = _stable_id(stream, payload)
    return event


def append_jsonl(stream: str, event: Dict[str, Any]) -> None:
    path = ensure_history_dir() / f"{stream}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, default=_json_default) + "\n")


def append_csv(stream: str, event: Dict[str, Any]) -> None:
    path = ensure_history_dir() / f"{stream}.csv"
    new_file = not path.exists() or path.stat().st_size == 0
    row = {
        "written_at": event.get("written_at", now_iso()),
        "event_id": event.get("event_id", ""),
        "stream": event.get("stream", stream),
        "source": event.get("source", ""),
        "payload_json": json.dumps(event.get("payload", {}), ensure_ascii=False, default=_json_default),
    }
    with path.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def append_event(stream: str, payload: Dict[str, Any] | None = None, source: str = "") -> None:
    try:
        event = _envelope(stream, payload or {}, source=source)
        append_jsonl(stream, event)
        append_csv(stream, event)
    except Exception:
        # Historia nigdy nie mo?e wywr?ci? logiki bota.
        pass


def append_records(stream: str, records: Iterable[Dict[str, Any]], source: str = "") -> int:
    count = 0
    for record in records or []:
        if not isinstance(record, dict):
            record = {"value": record}
        append_event(stream, record, source=source)
        count += 1
    return count
