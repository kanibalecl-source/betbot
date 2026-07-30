"""Build quality_training.csv from server history without modifying sources.

CSV files and SQLite databases are opened read-only. The output is a new,
derived file written atomically. Existing output is preserved unless the
operator explicitly passes --replace-derived.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from quality_upgrade_engine import DixonColesEngine, no_vig_probabilities
from quality_data_admission import (
    admission_reasons,
    allowed_sqlite_tables,
    canonical_event_key,
    canonical_timestamp,
    source_name_allowed,
    verify_settlement_evidence,
)
from storage_paths import DATA_DIR

try:
    from server_data_guard import sha256_file as _guard_sha256_file
except (ImportError, AttributeError):
    _guard_sha256_file = None


def sha256_file(path: Path) -> str:
    """Hash a source even on older production guards lacking this helper."""
    if _guard_sha256_file is not None:
        return _guard_sha256_file(path)
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


OUTPUT_NAMES = {
    "quality_training.csv",
    "quality_training.meta.json",
    "quality_shadow_state.json",
    "quality_shadow_state.candidate.json",
}
SKIP_PARTS = {"server_backups", "__pycache__", "fold_1", "fold_2", "fold_3"}
SETTLED_SOURCE_HINTS = (
    "results_history", "result_history", "settled", "settlement", "bet_history",
)


def _num(value: Any, default: float | None = None) -> float | None:
    try:
        if value in (None, ""):
            return default
        result = float(str(value).replace("%", "").replace(",", ".").strip())
        return result if result == result else default
    except (TypeError, ValueError):
        return default


def _prob(value: Any) -> float | None:
    result = _num(value)
    if result is None:
        return None
    if result > 1:
        result /= 100.0
    return result if 0 < result < 1 else None


def _first(row: Mapping[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        value = row.get(name)
        if value not in (None, "", "nan", "None", "null"):
            return value
    return None


def _target(row: Mapping[str, Any]) -> int | None:
    raw_value = _first(row, ("target", "won", "result", "outcome", "bet_result", "status"))
    value = str("" if raw_value is None else raw_value).strip().upper()
    if value in {"1", "TRUE", "WON", "WIN", "W", "GREEN", "CLOSED_WON"}:
        return 1
    if value in {"0", "FALSE", "LOST", "LOSS", "LOSE", "L", "RED", "CLOSED_LOST"}:
        return 0
    profit = _num(_first(row, ("profit", "zysk", "pnl")))
    if profit is not None and profit > 0:
        return 1
    if profit is not None and profit < 0:
        return 0
    return None


def _market(value: Any) -> str:
    key = str(value or "").upper().replace(".", "_").replace(" ", "_").replace("-", "_")
    aliases = {
        "1": "HOME_WIN", "HOME": "HOME_WIN", "HOME_WIN": "HOME_WIN",
        "X": "DRAW", "DRAW": "DRAW",
        "2": "AWAY_WIN", "AWAY": "AWAY_WIN", "AWAY_WIN": "AWAY_WIN",
        "BTTS": "BTTS_YES", "BTTS_TAK": "BTTS_YES", "BTTS_YES": "BTTS_YES",
        "BTTS_NIE": "BTTS_NO", "BTTS_NO": "BTTS_NO",
        "OVER_25": "OVER_2_5", "OVER25": "OVER_2_5", "OVER_2_5": "OVER_2_5",
        "UNDER_25": "UNDER_2_5", "UNDER25": "UNDER_2_5", "UNDER_2_5": "UNDER_2_5",
        "OVER_15": "OVER_1_5", "OVER_1_5": "OVER_1_5",
        "UNDER_15": "UNDER_1_5", "UNDER_1_5": "UNDER_1_5",
        "OVER_35": "OVER_3_5", "OVER_3_5": "OVER_3_5",
        "UNDER_35": "UNDER_3_5", "UNDER_3_5": "UNDER_3_5",
    }
    return aliases.get(key, key)


def _decode_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if not isinstance(value, str) or not value.strip().startswith("{"):
        return {}
    try:
        parsed = json.loads(value)
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    except Exception:
        return {}


def _merge_raw_json(row: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(row)
    for name in ("raw_json", "payload_json", "data_json", "prediction_json"):
        payload = _decode_mapping(row.get(name))
        for key, value in payload.items():
            if merged.get(key) in (None, ""):
                merged[key] = value
    return merged


def _market_probability(row: Mapping[str, Any], market: str) -> tuple[float | None, str]:
    direct = _prob(
        _first(
            row,
            (
                "market_probability_no_vig", "market_probability",
                "market_prob", "implied_probability",
            ),
        )
    )
    if direct is not None:
        return direct, "stored_probability"
    odds_map = {}
    for name in ("market_odds", "odds_1x2", "outcome_odds", "all_odds"):
        odds_map = _decode_mapping(row.get(name))
        if odds_map:
            break
    if odds_map:
        de_vig = no_vig_probabilities(odds_map, "power")
        aliases = {
            "HOME_WIN": ("HOME_WIN", "1", "HOME"),
            "DRAW": ("DRAW", "X"),
            "AWAY_WIN": ("AWAY_WIN", "2", "AWAY"),
        }
        for key in aliases.get(market, (market,)):
            if key in de_vig:
                return de_vig[key], "power_no_vig"
    odds = _num(_first(row, ("odds", "kurs_buk", "bookmaker_odds", "odd")))
    if odds is not None and odds > 1:
        return 1.0 / odds, "single_implied_with_vig"
    return None, "missing"


def transform_row(
    row: Mapping[str, Any],
    source: str,
    *,
    verified_evidence_hashes: set[str] | None = None,
    strict: bool = True,
) -> dict[str, Any] | None:
    row = _merge_raw_json(row)
    target = _target(row)
    if target is None:
        return None
    market = _market(_first(row, ("market", "typ", "signal", "pick", "bet_name")))
    current = _prob(
        _first(
            row,
            (
                "current_probability", "probability", "prawd_final",
                "model_probability", "predicted_prob", "confidence",
            ),
        )
    )
    home_xg = _num(_first(row, ("home_xg", "xg_home")))
    away_xg = _num(_first(row, ("away_xg", "xg_away")))
    if current is None or home_xg is None or away_xg is None or not market:
        return None
    dixon = DixonColesEngine().predict_market(market, home_xg, away_xg)
    if dixon is None:
        return None
    market_probability, market_method = _market_probability(row, market)
    if market_probability is None:
        return None
    odds = _num(_first(row, ("odds", "kurs_buk", "bookmaker_odds", "odd")))
    closing_odds = _num(
        _first(row, ("closing_odds", "close_odds", "closing_line_odds", "odds_close"))
    )
    league = str(
        _first(row, ("league", "liga", "competition", "tournament")) or "UNKNOWN"
    )
    fixture_id = str(_first(row, ("fixture_id", "event_id", "match_id", "id")) or "")
    timestamp = canonical_timestamp(
        _first(
            row,
            ("created_at", "timestamp", "date", "match_date", "kickoff", "updated_at"),
        )
    )
    transformed = {
        "timestamp": timestamp,
        "kickoff": canonical_timestamp(_first(row, ("match_date", "kickoff", "date"))),
        "source": source,
        "market": market,
        "league": league,
        "fixture_id": fixture_id,
        # Shadow-only identity features. They are intentionally excluded from
        # the immutable core admission digest for backward compatibility with
        # the existing server ledger.
        "home_team": str(_first(row, ("home_team", "home", "team_home")) or ""),
        "away_team": str(_first(row, ("away_team", "away", "team_away")) or ""),
        "bookmaker": str(_first(row, ("bookmaker", "bukmacher")) or ""),
        "selection": str(_first(row, ("selection", "outcome_name")) or market),
        "sport": str(_first(row, ("sport", "discipline")) or "football").lower(),
        "current_probability": round(current, 8),
        "dixon_coles_probability": round(dixon, 8),
        "market_probability": round(market_probability, 8),
        "market_probability_method": market_method,
        "odds": round(odds, 8) if odds is not None and odds > 1.0 else "",
        "closing_odds": (
            round(closing_odds, 8)
            if closing_odds is not None and closing_odds > 1.0
            else ""
        ),
        "home_xg": round(home_xg, 8),
        "away_xg": round(away_xg, 8),
        "data_quality": _num(
            _first(row, ("feature_completeness", "quality_data_completeness", "quality_score")), ""
        ),
        "lineup_available": _first(row, ("lineup_available", "lineups_available")) or "",
        "injuries_available": _first(row, ("injuries_available", "injury_data_available")) or "",
        "home_rest_days": _num(_first(row, ("home_rest_days", "rest_days_home")), ""),
        "away_rest_days": _num(_first(row, ("away_rest_days", "rest_days_away")), ""),
        "home_form_home": _num(_first(row, ("home_form_home", "home_home_form")), ""),
        "away_form_away": _num(_first(row, ("away_form_away", "away_away_form")), ""),
        "coach_change": _first(row, ("coach_change", "manager_change")) or "",
        "odds_observed_at": _first(row, ("odds_observed_at", "observed_at")) or "",
        "strategy_version": _first(row, ("strategy_version",)) or "",
        "model_version": _first(row, ("model_version",)) or "",
        "prediction_snapshot_id": _first(row, ("prediction_snapshot_id", "snapshot_id")) or "",
        "settlement_payload_sha256": _first(
            row, ("settlement_payload_sha256", "payload_sha256")
        ) or "",
        "settlement_evidence_hash": _first(
            row, ("settlement_evidence_hash", "evidence_hash")
        ) or "",
        "target": target,
    }
    transformed["record_id"] = canonical_event_key(transformed)
    if strict and admission_reasons(
        transformed, verified_evidence_hashes=verified_evidence_hashes
    ):
        return None
    return transformed


def _csv_rows(path: Path) -> Iterable[dict[str, Any]]:
    for encoding in ("utf-8-sig", "utf-8", "cp1250"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                yield from csv.DictReader(handle)
            return
        except UnicodeDecodeError:
            continue
        except Exception:
            return


def _sqlite_rows(path: Path) -> Iterable[tuple[str, dict[str, Any]]]:
    connection = None
    try:
        connection = sqlite3.connect(
            f"file:{path.as_posix()}?mode=ro", uri=True, timeout=30
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        allowed = allowed_sqlite_tables()
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for table in tables:
            if table not in allowed:
                continue
            safe_table = table.replace('"', '""')
            try:
                cursor = connection.execute(f'SELECT * FROM "{safe_table}"')
                for row in cursor:
                    yield table, dict(row)
            except sqlite3.DatabaseError:
                continue
    except sqlite3.DatabaseError:
        return
    finally:
        if connection is not None:
            connection.close()


def source_files(data_dir: Path) -> list[Path]:
    files = []
    for path in data_dir.rglob("*"):
        if not path.is_file() or path.name in OUTPUT_NAMES:
            continue
        if any(part in SKIP_PARTS for part in path.relative_to(data_dir).parts):
            continue
        suffix = path.suffix.lower()
        if suffix in {".sqlite3", ".db"} and source_name_allowed(path):
            files.append(path)
        elif suffix == ".csv" and any(
            hint in path.name.lower() for hint in SETTLED_SOURCE_HINTS
        ):
            files.append(path)
    return sorted(files, key=lambda item: str(item).lower())


def _enforce_admission_ledger(
    ledger_path: Path,
    records: list[dict[str, Any]],
    quarantined: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Persist immutable admitted payload identities and reject later mutation."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(ledger_path, timeout=30)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS training_admission_ledger (
        record_id TEXT PRIMARY KEY,
        payload_sha256 TEXT NOT NULL,
        admitted_at TEXT NOT NULL,
        payload_json TEXT NOT NULL
    );
    CREATE TRIGGER IF NOT EXISTS protect_training_admission_update
    BEFORE UPDATE ON training_admission_ledger
    BEGIN SELECT RAISE(ABORT, 'training admission is immutable'); END;
    CREATE TRIGGER IF NOT EXISTS protect_training_admission_delete
    BEFORE DELETE ON training_admission_ledger
    BEGIN SELECT RAISE(ABORT, 'training admission is immutable'); END;
    """)
    accepted: list[dict[str, Any]] = []
    immutable_conflicts = 0
    try:
        for row in records:
            canonical = {
                key: value
                for key, value in row.items()
                if key not in {"source", "home_team", "away_team"}
            }
            payload = json.dumps(
                canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            existing = connection.execute(
                "SELECT payload_sha256 FROM training_admission_ledger WHERE record_id=?",
                (row["record_id"],),
            ).fetchone()
            if existing and str(existing[0]) != digest:
                immutable_conflicts += 1
                quarantined.append({
                    "source": row.get("source", ""),
                    "record_id": row["record_id"],
                    "reasons": ["immutable_admission_payload_changed"],
                })
                continue
            if not existing:
                connection.execute(
                    "INSERT INTO training_admission_ledger "
                    "(record_id,payload_sha256,admitted_at,payload_json) VALUES (?,?,?,?)",
                    (
                        row["record_id"],
                        digest,
                        datetime.now(timezone.utc).isoformat(),
                        payload,
                    ),
                )
            accepted.append(row)
        connection.commit()
        return accepted, immutable_conflicts
    finally:
        connection.close()


def _conflicting_observation(
    existing: Mapping[str, Any], incoming: Mapping[str, Any]
) -> bool:
    if existing.get("target") != incoming.get("target"):
        return True
    exact = ("fixture_id", "market", "sport", "prediction_snapshot_id")
    if any(str(existing.get(key)) != str(incoming.get(key)) for key in exact):
        return True
    numeric = (
        "current_probability", "dixon_coles_probability", "market_probability",
        "odds", "home_xg", "away_xg",
    )
    for key in numeric:
        left, right = _num(existing.get(key)), _num(incoming.get(key))
        if left is None or right is None or abs(left - right) > 1e-8:
            return True
    return False


def build(data_dir: Path, output: Path, replace_derived: bool = False) -> dict[str, Any]:
    data_dir = data_dir.resolve()
    output = output.resolve()
    if output.exists() and not replace_derived:
        raise FileExistsError(
            f"Derived output already exists: {output}. Use --replace-derived explicitly."
        )
    sources = source_files(data_dir)
    hashes_before = {str(path): sha256_file(path) for path in sources}
    verified_by_path: dict[Path, set[str]] = {}
    evidence_errors_by_path: dict[Path, list[str]] = {}
    globally_verified_hashes: set[str] = set()
    for path in sources:
        if path.suffix.lower() not in {".sqlite3", ".db"}:
            continue
        verified, errors = verify_settlement_evidence(path)
        verified_by_path[path] = verified
        evidence_errors_by_path[path] = errors
        globally_verified_hashes.update(verified)
    allow_unverified_csv = os.getenv(
        "BETBOT_QUALITY_ALLOW_UNVERIFIED_CSV", "0"
    ).strip().lower() in {"1", "true", "yes", "on"}
    records: dict[str, dict[str, Any]] = {}
    quarantined: list[dict[str, Any]] = []
    conflicts: set[str] = set()
    scanned = 0
    for path in sources:
        relative = path.relative_to(data_dir).as_posix()
        verified_hashes = verified_by_path.get(path)
        evidence_errors = evidence_errors_by_path.get(path, [])
        if path.suffix.lower() == ".csv":
            for row in _csv_rows(path):
                scanned += 1
                transformed = transform_row(row, relative, strict=False)
                if transformed:
                    reasons = admission_reasons(
                        transformed,
                        verified_evidence_hashes=(
                            None if allow_unverified_csv else globally_verified_hashes
                        ),
                    )
                    if reasons:
                        quarantined.append({
                            "source": relative,
                            "record_id": transformed["record_id"],
                            "reasons": reasons,
                        })
                        continue
                    existing = records.get(transformed["record_id"])
                    if existing and _conflicting_observation(existing, transformed):
                        conflicts.add(transformed["record_id"])
                        records.pop(transformed["record_id"], None)
                        quarantined.append({
                            "source": relative,
                            "record_id": transformed["record_id"],
                            "reasons": ["conflicting_observation_across_sources"],
                        })
                    elif transformed["record_id"] not in conflicts:
                        records[transformed["record_id"]] = transformed
        else:
            for table, row in _sqlite_rows(path):
                scanned += 1
                source = f"{relative}::{table}"
                transformed = transform_row(
                    row, source, verified_evidence_hashes=verified_hashes, strict=False
                )
                if transformed:
                    reasons = admission_reasons(
                        transformed, verified_evidence_hashes=verified_hashes
                    )
                    if evidence_errors:
                        reasons.append("settlement_evidence_chain_invalid")
                    if reasons:
                        quarantined.append({
                            "source": source,
                            "record_id": transformed["record_id"],
                            "reasons": sorted(set(reasons)),
                        })
                        continue
                    existing = records.get(transformed["record_id"])
                    if existing and _conflicting_observation(existing, transformed):
                        conflicts.add(transformed["record_id"])
                        records.pop(transformed["record_id"], None)
                        quarantined.append({
                            "source": source,
                            "record_id": transformed["record_id"],
                            "reasons": ["conflicting_observation_across_sources"],
                        })
                    elif transformed["record_id"] not in conflicts:
                        records[transformed["record_id"]] = transformed
    hashes_after = {str(path): sha256_file(path) for path in sources}
    if hashes_before != hashes_after:
        raise RuntimeError("A source history file changed during read-only extraction.")
    ordered = sorted(
        records.values(),
        key=lambda row: (row["timestamp"], row["record_id"]),
    )
    ordered, immutable_conflicts = _enforce_admission_ledger(
        output.parent / "training_admission_ledger.sqlite3",
        ordered,
        quarantined,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    fields = [
        "timestamp", "kickoff", "source", "record_id", "fixture_id", "market",
        "league", "home_team", "away_team", "bookmaker", "selection", "sport",
        "current_probability", "dixon_coles_probability",
        "market_probability", "market_probability_method", "target",
        "odds", "closing_odds", "home_xg", "away_xg", "data_quality",
        "lineup_available", "injuries_available", "home_rest_days", "away_rest_days",
        "home_form_home", "away_form_away", "coach_change", "odds_observed_at",
        "strategy_version", "model_version", "prediction_snapshot_id",
        "settlement_payload_sha256", "settlement_evidence_hash",
    ]
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(ordered)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, output)
    metadata = {
        "status": "CREATED",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(data_dir),
        "output": str(output),
        "source_files": len(sources),
        "rows_scanned": scanned,
        "training_rows": len(ordered),
        "quarantined_rows": len(quarantined),
        "conflicting_event_keys": len(conflicts),
        "immutable_admission_conflicts": immutable_conflicts,
        "source_hashes_unchanged": True,
        "source_hashes": hashes_after,
    }
    metadata_path = (
        output.with_name("quality_training.meta.json")
        if output.name == "quality_training.csv"
        else output.with_suffix(".meta.json")
    )
    metadata_temp = metadata_path.with_suffix(".json.tmp")
    metadata_temp.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(metadata_temp, metadata_path)
    quarantine_path = output.with_name("quality_training.quarantine.jsonl")
    quarantine_temp = quarantine_path.with_suffix(".jsonl.tmp")
    with quarantine_temp.open("w", encoding="utf-8") as handle:
        for item in quarantined:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(quarantine_temp, quarantine_path)
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument("--output", default="")
    parser.add_argument("--replace-derived", action="store_true")
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    output = Path(args.output) if args.output else data_dir / "quality_training.csv"
    result = build(data_dir, output, replace_derived=args.replace_derived)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["training_rows"] < 30:
        print("WARNING: fewer than 30 complete settled rows; training will not run.")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
