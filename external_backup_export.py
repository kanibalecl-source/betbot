"""Optional encrypted-transport export to a user-provided presigned HTTPS URL.

Disabled unless BETBOT_EXTERNAL_BACKUP_UPLOAD_URL is configured.  It never
deletes source data and stages the archive outside the persistent volume.
"""
from __future__ import annotations

import hashlib
import http.client
import io
import json
import os
import shutil
import tarfile
import tempfile
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from storage_paths import get_data_dir


def _read(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _latest_verified_backup(data: Path) -> Path | None:
    root = data / "server_backups" / "deployments"
    if not root.is_dir():
        return None
    complete = [path for path in root.iterdir() if path.is_dir() and (path / "manifest.json").is_file()]
    return max(complete, key=lambda path: (path / "manifest.json").stat().st_mtime, default=None)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _upload_file(url: str, archive: Path, digest: str, bearer: str = "") -> int:
    """Stream a backup without loading the archive into process memory."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("External backup endpoint must be HTTPS")
    target = parsed.path or "/"
    if parsed.query:
        target += f"?{parsed.query}"
    connection = http.client.HTTPSConnection(parsed.hostname, parsed.port, timeout=300)
    try:
        connection.putrequest("PUT", target)
        connection.putheader("Content-Type", "application/gzip")
        connection.putheader("Content-Length", str(archive.stat().st_size))
        connection.putheader("X-Betbot-SHA256", digest)
        if bearer:
            connection.putheader("Authorization", f"Bearer {bearer}")
        connection.endheaders()
        with archive.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                connection.send(chunk)
        response = connection.getresponse()
        response.read(4096)
        return int(response.status)
    finally:
        connection.close()


def run_external_backup_if_due(
    data_dir: str | Path | None = None,
    *,
    force: bool = False,
) -> dict[str, Any]:
    data = Path(data_dir or get_data_dir()).resolve()
    status_path = data / "external_backup_status.json"
    upload_url = os.getenv("BETBOT_EXTERNAL_BACKUP_UPLOAD_URL", "").strip()
    if not upload_url:
        return {"status": "DISABLED_NO_UPLOAD_URL"}
    if not upload_url.lower().startswith("https://"):
        return {"status": "REFUSED_NON_HTTPS_URL"}
    previous = _read(status_path)
    if not force and previous.get("completed_at"):
        try:
            completed = datetime.fromisoformat(str(previous["completed_at"]).replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - completed < timedelta(hours=24):
                return {"status": "SKIPPED_NOT_DUE", **previous}
        except Exception:
            pass
    verified = _latest_verified_backup(data)
    if verified is None:
        return {"status": "SKIPPED_NO_VERIFIED_BACKUP"}
    files = sorted(path for path in verified.rglob("*") if path.is_file())
    total = sum(path.stat().st_size for path in files)
    max_bytes = int(os.getenv("BETBOT_EXTERNAL_BACKUP_MAX_BYTES", str(2 * 1024**3)))
    if total > max_bytes:
        return {"status": "REFUSED_SIZE_LIMIT", "bytes": total, "limit": max_bytes}
    temp_root = Path(tempfile.gettempdir()).resolve()
    reserve = max(128 * 1024**2, total // 10)
    if shutil.disk_usage(temp_root).free < total + reserve:
        return {"status": "SKIPPED_LOW_TEMP_SPACE", "bytes": total}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = temp_root / f"betbot_external_backup_{stamp}.tar.gz"
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_backup": verified.name,
        "files": [path.relative_to(verified).as_posix() for path in files],
    }
    try:
        with tarfile.open(archive, "w:gz") as bundle:
            for path in files:
                bundle.add(path, arcname=path.relative_to(verified).as_posix(), recursive=False)
            payload = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
            info = tarfile.TarInfo("backup_manifest.json")
            info.size = len(payload)
            bundle.addfile(info, io.BytesIO(payload))
        digest = _sha256_file(archive)
        bearer = os.getenv("BETBOT_EXTERNAL_BACKUP_BEARER", "").strip()
        code = _upload_file(upload_url, archive, digest, bearer)
        if not 200 <= code < 300:
            raise RuntimeError(f"Backup endpoint returned HTTP {code}")
        report = {
            "status": "UPLOADED",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "bytes": archive.stat().st_size,
            "source_bytes": total,
            "sha256": digest,
            "files": len(files),
        }
        temporary = status_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, status_path)
        return report
    finally:
        archive.unlink(missing_ok=True)
