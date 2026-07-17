from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable


CSV_PATTERNS = (
    "results_history.csv",
    "auto_all_picks_history.csv",
    "auto_low_picks_history.csv",
    "auto_risk_picks_history.csv",
    "ai_learning/ai_feature_store.csv",
    "ai_learning_low/ai_feature_store.csv",
    "ai_learning_risk/ai_feature_store.csv",
    "ai_learning/ai_learning_events.csv",
    "ai_learning_low/ai_learning_events.csv",
    "ai_learning_risk/ai_learning_events.csv",
    "history/*.csv",
    "history/*.jsonl",
)


def _fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"


def _row_key(row: dict[str, Any]) -> str:
    for name in ("event_id", "pick_key", "pick_id", "ai_id", "analysis_key"):
        value = str(row.get(name) or "").strip()
        if value:
            return f"{name}:{value}"
    stable = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _backup_file(path: Path, backup_root: Path, label: str) -> None:
    if not path.exists() or path.stat().st_size == 0:
        return
    relative = path.name
    destination = backup_root / label / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copy2(path, destination)


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists() or path.stat().st_size == 0:
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _merge_csv(target: Path, source: Path, backup_root: Path, label: str) -> int:
    source_fields, source_rows = _read_csv(source)
    if not source_rows:
        return 0
    if not target.exists() or target.stat().st_size == 0:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return len(source_rows)

    target_fields, target_rows = _read_csv(target)
    existing = {_row_key(row) for row in target_rows}
    additions = [row for row in source_rows if _row_key(row) not in existing]
    if not additions:
        return 0

    _backup_file(target, backup_root, label)
    fields = list(target_fields)
    for field in source_fields:
        if field not in fields:
            fields.append(field)
    for row in additions:
        for field in row:
            if field not in fields:
                fields.append(field)

    merged = target_rows + additions
    temporary = target.with_suffix(target.suffix + ".merge_tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(merged)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
    return len(additions)


def _merge_jsonl(target: Path, source: Path) -> int:
    if not source.exists() or source.stat().st_size == 0:
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    existing: set[str] = set()
    if target.exists():
        for line in target.read_text(encoding="utf-8").splitlines():
            try:
                existing.add(_row_key(json.loads(line)))
            except Exception:
                existing.add("raw:" + hashlib.sha256(line.encode("utf-8")).hexdigest())
    additions: list[str] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            key = _row_key(json.loads(line))
        except Exception:
            key = "raw:" + hashlib.sha256(line.encode("utf-8")).hexdigest()
        if key not in existing:
            existing.add(key)
            additions.append(line)
    if additions:
        with target.open("a", encoding="utf-8") as handle:
            for line in additions:
                handle.write(line + "\n")
    return len(additions)


def _columns(conn: sqlite3.Connection, schema: str, table: str) -> list[str]:
    return [str(row[1]) for row in conn.execute(f'PRAGMA {schema}.table_info("{table}")')]


def _merge_main_database(target: Path, source: Path, backup_root: Path, label: str) -> dict[str, int]:
    if not source.exists() or source.stat().st_size == 0:
        return {"picks": 0, "gpt": 0, "events": 0}
    if not target.exists() or target.stat().st_size == 0:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        conn = sqlite3.connect(target)
        try:
            picks = conn.execute("SELECT COUNT(*) FROM picks_history").fetchone()[0]
            gpt = conn.execute("SELECT COUNT(*) FROM gpt_analyses").fetchone()[0]
            events = conn.execute("SELECT COUNT(*) FROM learning_events").fetchone()[0]
        finally:
            conn.close()
        return {"picks": int(picks), "gpt": int(gpt), "events": int(events)}

    _backup_file(target, backup_root, label)
    conn = sqlite3.connect(target, timeout=30)
    conn.row_factory = sqlite3.Row
    before = {}
    try:
        for table in ("picks_history", "gpt_analyses", "learning_events"):
            before[table] = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        conn.execute("ATTACH DATABASE ? AS legacy", (str(source),))

        main_cols = _columns(conn, "main", "picks_history")
        legacy_cols = _columns(conn, "legacy", "picks_history")
        common = [c for c in main_cols if c in legacy_cols and c != "id"]
        quoted = ",".join(f'"{c}"' for c in common)
        conn.execute(
            f'INSERT OR IGNORE INTO main.picks_history ({quoted}) '
            f'SELECT {quoted} FROM legacy.picks_history'
        )

        settlement_fields = [
            c for c in (
                "updated_at", "status", "result", "profit", "roi", "home_goals",
                "away_goals", "result_score", "settlement_source", "settled_at",
            ) if c in main_cols and c in legacy_cols
        ]
        if settlement_fields:
            assignments = ",".join(
                f'"{c}"=(SELECT l."{c}" FROM legacy.picks_history l '
                f'WHERE l.pick_key=main.picks_history.pick_key)' for c in settlement_fields
            )
            conn.execute(
                f'UPDATE main.picks_history SET {assignments} '
                "WHERE UPPER(COALESCE(status,''))!='CLOSED' AND pick_key IN ("
                "SELECT l.pick_key FROM legacy.picks_history l "
                "WHERE UPPER(COALESCE(l.status,''))='CLOSED')"
            )

        for table, unique_column in (("gpt_analyses", "analysis_key"),):
            main_table_cols = _columns(conn, "main", table)
            legacy_table_cols = _columns(conn, "legacy", table)
            table_common = [c for c in main_table_cols if c in legacy_table_cols and c != "id"]
            if unique_column in table_common:
                names = ",".join(f'"{c}"' for c in table_common)
                conn.execute(f'INSERT OR IGNORE INTO main."{table}" ({names}) SELECT {names} FROM legacy."{table}"')

        existing_events = {
            hashlib.sha256(f"{r[0]}|{r[1]}|{r[2]}".encode("utf-8")).hexdigest()
            for r in conn.execute("SELECT created_at,event_type,payload_json FROM main.learning_events")
        }
        for row in conn.execute("SELECT created_at,event_type,payload_json FROM legacy.learning_events"):
            key = hashlib.sha256(f"{row[0]}|{row[1]}|{row[2]}".encode("utf-8")).hexdigest()
            if key not in existing_events:
                conn.execute(
                    "INSERT INTO main.learning_events(created_at,event_type,payload_json) VALUES(?,?,?)",
                    tuple(row),
                )
                existing_events.add(key)
        conn.commit()
        conn.execute("DETACH DATABASE legacy")
        after = {
            table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in before
        }
    finally:
        conn.close()
    return {
        "picks": int(after["picks_history"] - before["picks_history"]),
        "gpt": int(after["gpt_analyses"] - before["gpt_analyses"]),
        "events": int(after["learning_events"] - before["learning_events"]),
    }


def discover_legacy_data_dirs(base_dir: Path, data_dir: Path) -> list[Path]:
    found: list[Path] = []
    configured = os.getenv("KANIBAL_LEGACY_DATA_DIRS", "")
    for raw in configured.split(os.pathsep):
        path = Path(raw.strip()) if raw.strip() else None
        if path and path.is_dir():
            found.append(path)

    if os.getenv("KANIBAL_AUTO_DISCOVER_LEGACY", "1").lower() not in {"0", "false", "no", "off"}:
        for ancestor in list(base_dir.parents)[:3]:
            if ancestor.name.lower() in {"desktop", "documents", "users"}:
                continue
            for pattern in (
                "betbot-main/data/kanibal_persistent.sqlite3",
                "*/betbot-main/data/kanibal_persistent.sqlite3",
                "*/*/betbot-main/data/kanibal_persistent.sqlite3",
            ):
                try:
                    for database in ancestor.glob(pattern):
                        candidate = database.parent
                        if candidate.resolve() != data_dir.resolve():
                            found.append(candidate)
                except OSError:
                    continue

    unique: list[Path] = []
    seen: set[str] = set()
    for path in found:
        resolved = str(path.resolve()).lower()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique


def migrate_legacy_data(data_dir: Path, sources: Iterable[Path]) -> dict[str, Any]:
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    state_path = data_dir / ".legacy_migration_state.json"
    lock_path = data_dir / ".legacy_migration.lock"
    backup_root = data_dir / "legacy_backups"
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(lock_fd)
    except FileExistsError:
        try:
            if time.time() - lock_path.stat().st_mtime > 300:
                lock_path.unlink()
                lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(lock_fd)
            else:
                return {"status": "LOCKED", "sources": 0}
        except OSError:
            return {"status": "LOCKED", "sources": 0}

    try:
        try:
            state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        except Exception:
            state = {}
        processed = state.setdefault("processed", {})
        summary: dict[str, Any] = {"status": "OK", "sources": 0, "picks": 0, "events": 0, "csv_rows": 0}

        for source in sources:
            source = Path(source)
            database = source / "kanibal_persistent.sqlite3"
            if not source.is_dir() or not database.exists() or source.resolve() == data_dir.resolve():
                continue
            fingerprint = _fingerprint(database)
            source_key = str(source.resolve())
            if processed.get(source_key) == fingerprint:
                continue
            label = hashlib.sha1(source_key.encode("utf-8")).hexdigest()[:12]
            db_result = _merge_main_database(
                data_dir / "kanibal_persistent.sqlite3", database, backup_root, label
            )
            summary["picks"] += db_result["picks"]
            summary["events"] += db_result["events"]

            legacy_tracker = source / "bot_tracker.sqlite3"
            if legacy_tracker.exists():
                destination = backup_root / label / "bot_tracker.sqlite3"
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists():
                    shutil.copy2(legacy_tracker, destination)

            files: list[Path] = []
            for pattern in CSV_PATTERNS:
                files.extend(source.glob(pattern))
            for legacy_file in files:
                relative = legacy_file.relative_to(source)
                target_file = data_dir / relative
                if legacy_file.suffix.lower() == ".jsonl":
                    summary["csv_rows"] += _merge_jsonl(target_file, legacy_file)
                else:
                    summary["csv_rows"] += _merge_csv(target_file, legacy_file, backup_root, label)

            for model in source.glob("ai_learning*/ai_model_state*.json"):
                destination = backup_root / label / model.parent.name / model.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists():
                    shutil.copy2(model, destination)

            processed[source_key] = fingerprint
            summary["sources"] += 1

        state["last_run_epoch"] = time.time()
        state["last_summary"] = summary
        temporary = state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, state_path)
        return summary
    finally:
        lock_path.unlink(missing_ok=True)


def migrate_discovered_legacy_data(base_dir: Path, data_dir: Path) -> dict[str, Any]:
    if any(os.getenv(name) for name in ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID")):
        return {"status": "SERVER_SKIPPED", "sources": 0}
    sources = discover_legacy_data_dirs(Path(base_dir), Path(data_dir))
    return migrate_legacy_data(Path(data_dir), sources)
