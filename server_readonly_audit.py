"""Read-only server audit for persistent storage and training history."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from server_data_guard import critical_files, sha256_file
from storage_paths import (
    BASE_DIR,
    DATA_DIR,
    persistent_storage_configured,
)


def sqlite_summary(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"path": str(path), "tables": {}}
    connection = None
    try:
        connection = sqlite3.connect(
            f"file:{path.as_posix()}?mode=ro", uri=True, timeout=30
        )
        connection.execute("PRAGMA query_only=ON")
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for table in tables:
            safe_table = table.replace('"', '""')
            try:
                count = connection.execute(
                    f'SELECT COUNT(*) FROM "{safe_table}"'
                ).fetchone()[0]
                columns = [
                    row[1]
                    for row in connection.execute(
                        f'PRAGMA table_info("{safe_table}")'
                    )
                ]
                result["tables"][table] = {
                    "rows": int(count),
                    "columns": columns,
                }
            except sqlite3.DatabaseError as exc:
                result["tables"][table] = {"error": str(exc)}
    except sqlite3.DatabaseError as exc:
        result["error"] = str(exc)
    finally:
        if connection is not None:
            connection.close()
    return result


def audit() -> dict[str, Any]:
    data_dir = DATA_DIR.resolve()
    code_data = (BASE_DIR / "data").resolve()
    backup_root = data_dir / "server_backups"
    files = critical_files(data_dir, backup_root)
    bundled_files = []
    if code_data.exists() and code_data != data_dir:
        bundled_files = [
            path.relative_to(BASE_DIR).as_posix()
            for path in code_data.rglob("*")
            if path.is_file()
        ]
    environment = {
        name: os.getenv(name, "")
        for name in (
            "RAILWAY_ENVIRONMENT",
            "RAILWAY_PROJECT_ID",
            "RAILWAY_SERVICE_ID",
            "RAILWAY_VOLUME_MOUNT_PATH",
            "PERSISTENT_DATA_DIR",
            "KANIBAL_DATA_DIR",
            "KANIBAL_REQUIRE_PERSISTENT_STORAGE",
            "BETBOT_QUALITY_SHADOW",
            "BETBOT_QUALITY_STATE",
        )
    }
    report = {
        "mode": "READ_ONLY_NO_WRITES",
        "base_dir": str(BASE_DIR.resolve()),
        "data_dir": str(data_dir),
        "code_data_dir": str(code_data),
        "data_outside_deploy": data_dir != code_data,
        "persistent_storage_configured": persistent_storage_configured(),
        "environment": environment,
        "bundled_data_files": bundled_files,
        "critical_file_count": len(files),
        "critical_files": [
            {
                "path": path.relative_to(data_dir).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ],
        "sqlite": [
            sqlite_summary(path)
            for path in files
            if path.suffix.lower() in {".sqlite3", ".db"}
        ],
    }
    blockers = []
    if not report["persistent_storage_configured"]:
        blockers.append("persistent_storage_not_confirmed")
    if bundled_files:
        blockers.append("deployment_contains_bundled_data")
    if not files:
        blockers.append("no_persistent_history_detected")
    report["deployment_status"] = "BLOCKED" if blockers else "AUDIT_PASSED"
    report["blockers"] = blockers
    return report


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
