"""Atomic versioned runtime health artifacts; no secrets and no source mutation."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from storage_paths import get_data_dir

RUNTIME_SCHEMA = "betbot.runtime_health.v8.1"
QUALITY_SCHEMA = "betbot.quality_governance_health.v8.1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return dict(value) if isinstance(value, Mapping) else {}
    except Exception:
        return {}


def quality_health_path(data_dir: str | Path | None = None) -> Path:
    return Path(data_dir or get_data_dir()).resolve() / "quality_retraining" / "quality_governance_health_v81.json"


def runtime_health_path(data_dir: str | Path | None = None) -> Path:
    return Path(data_dir or get_data_dir()).resolve() / "runtime_health.json"
