"""Fail-closed protection for persistent history during server redeploys."""
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


SERVER_ENV_NAMES = ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "KANIBAL_SERVER_MODE")
BACKUP_PATTERNS = (
    "*.sqlite3", "*.db", "results_history.csv", "*_history.csv",
    "history/**/*", "ai_learning*/**/*", "enterprise/**/*",
    "gpt_analysis_report*.json",
)


def _is_server() -> bool:
    return any(os.getenv(name, "").strip() for name in SERVER_ENV_NAMES)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _deployment_key() -> str:
    raw = os.getenv("RAILWAY_DEPLOYMENT_ID", "").strip()
    if raw:
        return re.sub(r"[^A-Za-z0-9_.-]", "_", raw)[:120]
    return datetime.now(timezone.utc).strftime("startup_%Y%m%dT%H%M%S_%fZ")


def _critical_files(data_dir: Path, backup_root: Path) -> list[Path]:
    files: set[Path] = set()
    for pattern in BACKUP_PATTERNS:
        for path in data_dir.glob(pattern):
            if path.is_file() and backup_root not in path.parents:
                files.add(path)
    return sorted(files, key=lambda path: str(path).lower())


def _backup_sqlite(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True, timeout=30)
    target_conn = sqlite3.connect(destination, timeout=30)
    try:
        source_conn.backup(target_conn)
        target_conn.commit()
    finally:
        target_conn.close()
        source_conn.close()


def prepare_server_data_backup(
    data_dir: str | Path | None = None,
    base_dir: str | Path | None = None,
    deployment_key: str | None = None,
    force_server: bool = False,
) -> dict[str, Any]:
    """Validate external storage and create a non-destructive pre-start backup.

    No source file is opened for writing. Existing backups are never replaced.
    A repeated process start for the same Railway deployment is idempotent.
    """
    if not (force_server or _is_server()):
        return {"status": "LOCAL_SKIPPED"}

    if data_dir is None:
        require_persistent_storage_on_server()
    data_path = Path(data_dir or DATA_DIR).resolve()
    code_path = Path(base_dir or BASE_DIR).resolve()
    bundled_path = (code_path / "data").resolve()
    railway_mount = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    try:
        confirmed_railway_volume = bool(railway_mount) and data_path == Path(railway_mount).resolve()
    except Exception:
        confirmed_railway_volume = False
    if (data_path == bundled_path or code_path in data_path.parents) and not confirmed_railway_volume:
        raise RuntimeError("Katalog danych serwera znajduje się wewnątrz deploymentu; start przerwany.")

    bundled_files = (
        [p for p in bundled_path.rglob("*") if p.is_file()]
        if bundled_path.exists() and not (confirmed_railway_volume and bundled_path == data_path)
        else []
    )
    if bundled_files:
        raise RuntimeError("Paczka serwerowa zawiera katalog data; start przerwany, aby nie nadpisać Volume.")

    data_path.mkdir(parents=True, exist_ok=True)
    backup_root = data_path / "server_backups" / "deployments"
    backup_root.mkdir(parents=True, exist_ok=True)
    key = deployment_key or _deployment_key()
    destination_root = backup_root / key
    manifest_path = destination_root / "manifest.json"
    if manifest_path.exists():
        return {"status": "ALREADY_BACKED_UP", "deployment": key, "backup": str(destination_root)}
    if destination_root.exists():
        raise RuntimeError(f"Niekompletna kopia bezpieczeństwa deploymentu: {destination_root}")

    destination_root.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, Any] = {
        "deployment": key,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(data_path),
        "files": [],
    }
    for source in _critical_files(data_path, backup_root):
        relative = source.relative_to(data_path)
        destination = destination_root / relative
        before_hash = _sha256(source)
        if source.suffix.lower() in {".sqlite3", ".db"}:
            _backup_sqlite(source, destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        after_hash = _sha256(source)
        if before_hash != after_hash:
            raise RuntimeError(f"Plik źródłowy zmienił się podczas backupu: {relative}")
        manifest["files"].append({
            "path": relative.as_posix(),
            "size": source.stat().st_size,
            "source_sha256": after_hash,
            "backup_sha256": _sha256(destination),
        })

    temporary = destination_root / "manifest.tmp"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, manifest_path)
    return {
        "status": "BACKUP_CREATED",
        "deployment": key,
        "files": len(manifest["files"]),
        "backup": str(destination_root),
    }


if __name__ == "__main__":
    print(prepare_server_data_backup())
