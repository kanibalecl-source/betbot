"""Fail-closed, non-destructive protection for persistent server history."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from storage_paths import BASE_DIR, DATA_DIR, require_persistent_storage_on_server


CRITICAL_PATTERNS = (
    "*.sqlite3",
    "*.db",
    "results_history.csv",
    "*_history.csv",
    "history/**/*",
    "ai_learning*/**/*",
    "enterprise/**/*",
    "gpt_analysis_report*.json",
)

BACKUP_REUSE_HOURS_ENV = "BETBOT_SERVER_BACKUP_REUSE_HOURS"
BACKUP_KEEP_ENV = "BETBOT_SERVER_BACKUP_KEEP"
BACKUP_EMERGENCY_REUSE_HOURS_ENV = "BETBOT_SERVER_BACKUP_EMERGENCY_REUSE_HOURS"
DEFAULT_BACKUP_REUSE_HOURS = 0
DEFAULT_BACKUP_KEEP = 5
DEFAULT_BACKUP_EMERGENCY_REUSE_HOURS = 24
MIN_FREE_RESERVE_BYTES = 64 * 1024 * 1024
LOW_SPACE_MIN_FREE_RESERVE_BYTES = 48 * 1024 * 1024
LOW_SPACE_BACKUP_KEEP = 2


def _server_mode() -> bool:
    return any(
        os.getenv(name, "").strip()
        for name in ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "KANIBAL_SERVER_MODE")
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _deployment_key() -> str:
    value = os.getenv("RAILWAY_DEPLOYMENT_ID", "").strip()
    if value:
        return re.sub(r"[^A-Za-z0-9_.-]", "_", value)[:120]
    return datetime.now(timezone.utc).strftime("startup_%Y%m%dT%H%M%S_%fZ")


def _int_env(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return max(minimum, default)


def _complete_backups(backup_root: Path) -> list[Path]:
    complete = [
        path
        for path in backup_root.iterdir()
        if path.is_dir() and (path / "manifest.json").is_file()
    ]
    return sorted(
        complete,
        key=lambda path: (path / "manifest.json").stat().st_mtime,
        reverse=True,
    )


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _complete_full_backups(backup_root: Path) -> list[Path]:
    return [
        path
        for path in _complete_backups(backup_root)
        if _read_manifest(path).get("kind", "full") == "full"
    ]


def _backup_age_hours(path: Path) -> float:
    created = datetime.fromtimestamp(
        (path / "manifest.json").stat().st_mtime, timezone.utc
    )
    return max(0.0, (datetime.now(timezone.utc) - created).total_seconds() / 3600)


def _remove_verified_backup(path: Path, backup_root: Path) -> None:
    resolved = path.resolve()
    root = backup_root.resolve()
    if resolved.parent != root or not (resolved / "manifest.json").is_file():
        raise RuntimeError(f"Refusing to prune unverified backup path: {path}")
    shutil.rmtree(resolved)


def _prune_complete_backups(backup_root: Path, keep: int) -> list[str]:
    # Reference manifests are tiny and may point to an older full backup. Only
    # prune full snapshots here so a reference can never become dangling.
    complete = _complete_full_backups(backup_root)
    removed: list[str] = []
    for path in complete[max(1, keep):]:
        _remove_verified_backup(path, backup_root)
        removed.append(path.name)
    return removed


def _backup_matches_sources(backup: Path, data_path: Path, sources: list[Path]) -> bool:
    manifest = _read_manifest(backup)
    entries = manifest.get("files")
    if not isinstance(entries, list):
        return False
    expected = {
        str(entry.get("path")): entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("path")
    }
    current_paths = {source.relative_to(data_path).as_posix() for source in sources}
    if set(expected) != current_paths:
        return False
    for source in sources:
        relative = source.relative_to(data_path).as_posix()
        entry = expected[relative]
        if int(entry.get("size", -1)) != source.stat().st_size:
            return False
        if str(entry.get("source_sha256", "")) != sha256_file(source):
            return False
    return True


def _create_reference_manifest(
    destination_root: Path,
    manifest_path: Path,
    data_path: Path,
    key: str,
    reused_backup: Path,
    free_bytes: int,
    required_bytes: int,
) -> None:
    destination_root.mkdir(parents=True, exist_ok=False)
    manifest = {
        "kind": "reference",
        "deployment": key,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(data_path),
        "reused_backup": reused_backup.name,
        "reason": "identical_verified_snapshot_reused_due_to_low_space",
        "free_bytes": free_bytes,
        "required_bytes": required_bytes,
        "files": [],
    }
    temporary = destination_root / "manifest.tmp"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, manifest_path)


def critical_files(data_dir: Path, backup_root: Path | None = None) -> list[Path]:
    files: set[Path] = set()
    for pattern in CRITICAL_PATTERNS:
        for path in data_dir.glob(pattern):
            if not path.is_file():
                continue
            if backup_root is not None and backup_root in path.parents:
                continue
            files.add(path)
    return sorted(files, key=lambda item: str(item).lower())


def snapshot_hashes(data_dir: str | Path) -> dict[str, dict[str, Any]]:
    data_path = Path(data_dir).resolve()
    backup_root = data_path / "server_backups"
    return {
        path.relative_to(data_path).as_posix(): {
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in critical_files(data_path, backup_root)
    }


def _backup_sqlite(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(
        f"file:{source.as_posix()}?mode=ro", uri=True, timeout=30
    )
    destination_connection = sqlite3.connect(destination, timeout=30)
    try:
        source_connection.backup(destination_connection)
        destination_connection.commit()
    finally:
        destination_connection.close()
        source_connection.close()


def prepare_server_data_backup(
    data_dir: str | Path | None = None,
    base_dir: str | Path | None = None,
    deployment_key: str | None = None,
    force_server: bool = False,
) -> dict[str, Any]:
    """Validate the Volume and create an immutable pre-start backup."""
    if not (force_server or _server_mode()):
        return {"status": "LOCAL_SKIPPED"}
    if data_dir is None:
        require_persistent_storage_on_server()
    data_path = Path(data_dir or DATA_DIR).resolve()
    code_data = (Path(base_dir or BASE_DIR) / "data").resolve()
    railway_mount = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    confirmed_same_mount = False
    if railway_mount:
        try:
            confirmed_same_mount = data_path == Path(railway_mount).resolve()
        except Exception:
            confirmed_same_mount = False
    if data_path == code_data and not confirmed_same_mount:
        raise RuntimeError("Server data resolves inside deployment; startup blocked.")
    if code_data.exists() and code_data != data_path:
        bundled = [path for path in code_data.rglob("*") if path.is_file()]
        if bundled:
            raise RuntimeError("Deployment contains data files; startup blocked.")

    data_path.mkdir(parents=True, exist_ok=True)
    backup_root = data_path / "server_backups" / "deployments"
    backup_root.mkdir(parents=True, exist_ok=True)
    key = deployment_key or _deployment_key()
    destination_root = backup_root / key
    manifest_path = destination_root / "manifest.json"
    if manifest_path.exists():
        return {
            "status": "ALREADY_BACKED_UP",
            "deployment": key,
            "backup": str(destination_root),
        }
    if destination_root.exists():
        raise RuntimeError(f"Incomplete deployment backup exists: {destination_root}")

    complete = _complete_full_backups(backup_root)
    latest = complete[0] if complete else None
    reuse_hours = _int_env(
        BACKUP_REUSE_HOURS_ENV, DEFAULT_BACKUP_REUSE_HOURS, minimum=0
    )
    if latest is not None and reuse_hours > 0 and _backup_age_hours(latest) <= reuse_hours:
        return {
            "status": "RECENT_BACKUP_REUSED",
            "deployment": key,
            "backup": str(latest),
            "backup_age_hours": round(_backup_age_hours(latest), 3),
            "reuse_hours": reuse_hours,
        }

    sources = critical_files(data_path, backup_root)
    expected_bytes = sum(source.stat().st_size for source in sources)
    free_bytes = shutil.disk_usage(data_path).free
    reserve_bytes = max(MIN_FREE_RESERVE_BYTES, expected_bytes // 20)
    required_bytes = expected_bytes + reserve_bytes
    low_space_backup = False
    if latest is not None and free_bytes < required_bytes:
        emergency_hours = _int_env(
            BACKUP_EMERGENCY_REUSE_HOURS_ENV,
            DEFAULT_BACKUP_EMERGENCY_REUSE_HOURS,
            minimum=0,
        )
        latest_age = _backup_age_hours(latest)
        if (
            emergency_hours > 0
            and latest_age <= emergency_hours
            and _backup_matches_sources(latest, data_path, sources)
        ):
            _create_reference_manifest(
                destination_root,
                manifest_path,
                data_path,
                key,
                latest,
                free_bytes,
                required_bytes,
            )
            return {
                "status": "IDENTICAL_BACKUP_REUSED_LOW_SPACE",
                "deployment": key,
                "backup": str(destination_root),
                "reused_backup": str(latest),
                "backup_age_hours": round(latest_age, 3),
                "verified_files": len(sources),
                "free_bytes": free_bytes,
                "required_bytes": required_bytes,
            }
        constrained_required_bytes = expected_bytes + LOW_SPACE_MIN_FREE_RESERVE_BYTES
        if free_bytes >= constrained_required_bytes:
            # A complete backup still fits, but the normal 5% reserve does not.
            # Continue only with a fixed safety margin. Old backups are pruned
            # strictly after the new manifest has been written successfully.
            low_space_backup = True
        else:
            raise RuntimeError(
                "Insufficient space for a deployment-specific backup and no identical "
                "fresh snapshot can be reused; startup blocked "
                f"(required={required_bytes}, constrained_required="
                f"{constrained_required_bytes}, free={free_bytes})."
            )

    destination_root.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, Any] = {
        "kind": "full",
        "deployment": key,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(data_path),
        "files": [],
    }
    for source in sources:
        relative = source.relative_to(data_path)
        destination = destination_root / relative
        before = sha256_file(source)
        if source.suffix.lower() in {".sqlite3", ".db"}:
            _backup_sqlite(source, destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        after = sha256_file(source)
        if before != after:
            raise RuntimeError(f"Source changed while backing up: {relative}")
        manifest["files"].append({
            "path": relative.as_posix(),
            "size": source.stat().st_size,
            "source_sha256": after,
            "backup_sha256": sha256_file(destination),
        })
    temporary = destination_root / "manifest.tmp"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, manifest_path)
    removed = _prune_complete_backups(
        backup_root,
        _int_env(BACKUP_KEEP_ENV, DEFAULT_BACKUP_KEEP, minimum=1),
    )
    if low_space_backup:
        # The new snapshot is complete and verified at this point, so reducing
        # retention cannot leave the service without a usable full backup.
        removed.extend(
            name
            for name in _prune_complete_backups(
                backup_root,
                LOW_SPACE_BACKUP_KEEP,
            )
            if name not in removed
        )
    return {
        "status": "BACKUP_CREATED",
        "deployment": key,
        "files": len(manifest["files"]),
        "backup": str(destination_root),
        "pruned_backups": removed,
        "low_space_backup": low_space_backup,
    }
