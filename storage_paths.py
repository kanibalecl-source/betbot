from __future__ import annotations

import os
import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def get_data_dir() -> Path:
    candidates = []
    for env_name in ("KANIBAL_DATA_DIR", "PERSISTENT_DATA_DIR", "RAILWAY_VOLUME_MOUNT_PATH"):
        configured = os.getenv(env_name, "").strip()
        if configured:
            candidates.append(Path(configured))
    if Path("/data").exists():
        candidates.append(Path("/data"))
    candidates.append(BASE_DIR / "data")

    for candidate in candidates:
        if _is_writable_dir(candidate):
            return candidate

    fallback = BASE_DIR / "data"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


DATA_DIR = get_data_dir()


def migrate_local_data_once() -> None:
    local_data = BASE_DIR / "data"
    target = DATA_DIR
    if local_data.resolve() == target.resolve() or not local_data.exists():
        return

    marker = target / ".kanibal_data_migrated"
    if marker.exists():
        return

    for source in local_data.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(local_data)
        destination = target / relative
        if destination.exists() and destination.stat().st_size > 0:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    marker.write_text("ok", encoding="utf-8")


migrate_local_data_once()
