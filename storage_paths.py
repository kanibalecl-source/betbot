from __future__ import annotations

import os
import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".write_probe_{os.getpid()}"
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
            configured_path = Path(configured)
            candidates.append(configured_path)
            normalized = str(configured_path).replace("\\", "/").rstrip("/")
            railway_runtime = any(
                os.getenv(name, "").strip()
                for name in ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID")
            )
            if railway_runtime and normalized == "/data":
                return configured_path
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


def _is_server() -> bool:
    return any(
        os.getenv(name, "").strip()
        for name in ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "KANIBAL_SERVER_MODE")
    )


def persistent_storage_configured() -> bool:
    """Return True only when server data is outside the deploy directory."""
    railway_mount = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    try:
        confirmed_mount = bool(railway_mount) and DATA_DIR.resolve() == Path(railway_mount).resolve()
    except Exception:
        confirmed_mount = False
    configured_external = any(
        os.getenv(name, "").strip()
        for name in ("KANIBAL_DATA_DIR", "PERSISTENT_DATA_DIR")
    )
    outside_deploy = DATA_DIR.resolve() != (BASE_DIR / "data").resolve()
    standard_volume = str(DATA_DIR).replace("\\", "/").rstrip("/") == "/data"
    return confirmed_mount or standard_volume or (outside_deploy and configured_external)


def require_persistent_storage_on_server() -> None:
    """Fail closed instead of starting against ephemeral server storage."""
    strict = os.getenv("KANIBAL_REQUIRE_PERSISTENT_STORAGE", "1").strip().lower() not in {
        "0", "false", "no", "off"
    }
    if _is_server() and strict and not persistent_storage_configured():
        raise RuntimeError(
            "Persistent server storage is not configured. Attach Railway Volume "
            "and set PERSISTENT_DATA_DIR=/data. Startup stopped to protect history."
        )


def migrate_local_data_once() -> None:
    # The mounted server Volume is authoritative. A deployment must never seed
    # or merge it from files bundled with application code.
    if _is_server():
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
