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


def persistent_storage_configured() -> bool:
    """Return True only when data lives outside the deploy directory."""
    configured = any(
        os.getenv(name, "").strip()
        for name in ("KANIBAL_DATA_DIR", "PERSISTENT_DATA_DIR", "RAILWAY_VOLUME_MOUNT_PATH")
    )
    outside_deploy = DATA_DIR.resolve() != (BASE_DIR / "data").resolve()
    # Railway commonly mounts a Volume at /data without exposing its mount path
    # as an application variable. get_data_dir() has already verified that this
    # directory exists and is writable, so accept that standard mount directly.
    standard_volume = str(DATA_DIR).replace("\\", "/").rstrip("/") == "/data"
    return outside_deploy and (configured or standard_volume)


def require_persistent_storage_on_server() -> None:
    """Fail closed on a server that has no mounted persistent data directory."""
    is_server = any(
        os.getenv(name, "").strip()
        for name in ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "KANIBAL_SERVER_MODE")
    )
    strict = os.getenv("KANIBAL_REQUIRE_PERSISTENT_STORAGE", "1").strip().lower() not in {
        "0", "false", "no", "off"
    }
    if is_server and strict and not persistent_storage_configured():
        raise RuntimeError(
            "Brak trwałego katalogu danych. Podłącz Railway Volume i ustaw "
            "PERSISTENT_DATA_DIR/RAILWAY_VOLUME_MOUNT_PATH; start został zatrzymany, "
            "aby historia i nauka nie zniknęły po redeployu."
        )


def migrate_local_data_once() -> None:
    # A server deploy must never seed or merge its mounted Volume from files
    # bundled with application code. Server history is authoritative.
    if any(os.getenv(name, "").strip() for name in (
        "RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "KANIBAL_SERVER_MODE"
    )):
        return
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

try:
    from legacy_data_migration import migrate_discovered_legacy_data

    LEGACY_MIGRATION_SUMMARY = migrate_discovered_legacy_data(BASE_DIR, DATA_DIR)
except Exception as exc:
    LEGACY_MIGRATION_SUMMARY = {"status": "ERROR", "error": str(exc)}
