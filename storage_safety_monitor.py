"""Persistent-volume capacity alerts without deleting active data."""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from storage_paths import get_data_dir


def check_storage_health(data_dir: str | Path | None = None) -> dict[str, Any]:
    path = Path(data_dir or get_data_dir()).resolve()
    usage = shutil.disk_usage(path)
    percent = usage.used / max(1, usage.total) * 100.0
    warning = float(os.getenv("BETBOT_STORAGE_WARNING_PERCENT", "75"))
    critical = float(os.getenv("BETBOT_STORAGE_CRITICAL_PERCENT", "85"))
    if percent >= critical:
        status = "CRITICAL"
    elif percent >= warning:
        status = "WARNING"
    else:
        status = "OK"
    report = {
        "status": status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "path": str(path),
        "used_percent": round(percent, 2),
        "free_bytes": usage.free,
        "warning_percent": warning,
        "critical_percent": critical,
        "automatic_deletion": False,
    }
    target = path / "storage_health_alert.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, target)
    return report
