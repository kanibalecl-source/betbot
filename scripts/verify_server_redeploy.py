"""Offline two-redeploy simulation against a copied persistent data set."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_rows(path: Path) -> int:
    if not path.exists() or not path.stat().st_size:
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def state(data: Path) -> dict:
    database = data / "kanibal_persistent.sqlite3"
    conn = sqlite3.connect(database)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(picks_history)")}
    stable = [name for name in (
        "pick_key", "status", "result", "odds", "probability", "stake",
        "profit", "roi", "result_score", "settlement_source", "settled_at",
    ) if name in columns]
    rows = conn.execute(
        f"SELECT {','.join(stable)} FROM picks_history ORDER BY pick_key"
    ).fetchall()
    events = conn.execute("SELECT COUNT(1) FROM learning_events").fetchone()[0]
    conn.close()
    logical_hash = hashlib.sha256(json.dumps(rows, default=str).encode("utf-8")).hexdigest()
    tracked_files = []
    for pattern in ("results_history.csv", "history/**/*", "ai_learning*/**/*", "enterprise/**/*"):
        tracked_files.extend(path for path in data.glob(pattern) if path.is_file())
    return {
        "picks": len(rows),
        "closed": sum(1 for row in rows if str(row[stable.index("status")]).upper() == "CLOSED") if "status" in stable else 0,
        "picks_logical_sha256": logical_hash,
        "learning_events": events,
        "results_csv_rows": csv_rows(data / "results_history.csv"),
        "file_hashes": {path.relative_to(data).as_posix(): file_hash(path) for path in sorted(set(tracked_files))},
    }


def run_deploy(code: Path, volume: Path, deployment: str) -> str:
    env = os.environ.copy()
    env.update({
        "RAILWAY_ENVIRONMENT": "production-simulation",
        "RAILWAY_PROJECT_ID": "offline-safety-test",
        "RAILWAY_DEPLOYMENT_ID": deployment,
        "PERSISTENT_DATA_DIR": str(volume),
        "KANIBAL_REQUIRE_PERSISTENT_STORAGE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    snippet = (
        "import storage_paths; storage_paths.require_persistent_storage_on_server(); "
        "from server_data_guard import prepare_server_data_backup; print(prepare_server_data_backup()); "
        "import agi_storage,database; agi_storage.init_storage(); database.init_db(); "
        "print('STARTUP_PREFLIGHT_OK', storage_paths.DATA_DIR)"
    )
    completed = subprocess.run(
        [sys.executable, "-B", "-c", snippet], cwd=code, env=env,
        text=True, capture_output=True, timeout=60,
    )
    if completed.returncode:
        raise RuntimeError(f"Deploy simulation failed:\n{completed.stdout}\n{completed.stderr}")
    return completed.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-dir", type=Path, required=True)
    parser.add_argument("--seed-data", type=Path, required=True)
    args = parser.parse_args()
    code = args.code_dir.resolve()
    seed = args.seed_data.resolve()
    if (code / "data").exists():
        raise RuntimeError("Server package contains data directory")
    with tempfile.TemporaryDirectory(prefix="kanibal-redeploy-") as temporary:
        volume = Path(temporary) / "volume"
        shutil.copytree(seed, volume)
        (volume / ".legacy_migration_state.json").unlink(missing_ok=True)
        before = state(volume)
        first_output = run_deploy(code, volume, "simulation-deploy-1")
        after_first = state(volume)
        second_output = run_deploy(code, volume, "simulation-deploy-2")
        after_second = state(volume)
        if before != after_first or before != after_second:
            raise AssertionError(json.dumps({
                "before": before, "after_first": after_first, "after_second": after_second,
            }, ensure_ascii=False, indent=2))
        manifests = list((volume / "server_backups" / "deployments").glob("*/manifest.json"))
        if len(manifests) != 2:
            raise AssertionError(f"Expected 2 deployment backups, got {len(manifests)}")
        print(json.dumps({
            "status": "REDEPLOY_SIMULATION_OK",
            "state": before,
            "backups": len(manifests),
            "deploy_1": first_output,
            "deploy_2": second_output,
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
