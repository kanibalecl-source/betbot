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
    value = str(
        _first(row, ("target", "won", "result", "outcome", "bet_result", "status"))
        or ""
    ).strip().upper()
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


def transform_row(row: Mapping[str, Any], source: str) -> dict[str, Any] | None:
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
    timestamp = str(
        _first(
            row,
            ("created_at", "timestamp", "date", "match_date", "kickoff", "updated_at"),
        )
        or ""
    )
    identity = "|".join(
        str(_first(row, names) or "")
        for names in (
            ("pick_key", "ai_id", "fixture_id", "id"),
            ("match", "mecz", "match_name"),
            ("market", "typ", "signal"),
            ("odds", "kurs_buk"),
        )
    )
    fingerprint = hashlib.sha256(
        f"{source}|{identity}".encode("utf-8", errors="ignore")
    ).hexdigest()[:32]
    return {
        "timestamp": timestamp,
        "source": source,
        "record_id": fingerprint,
        "market": market,
        "current_probability": round(current, 8),
        "dixon_coles_probability": round(dixon, 8),
        "market_probability": round(market_probability, 8),
        "market_probability_method": market_method,
        "target": target,
    }


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
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for table in tables:
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
        if suffix in {".sqlite3", ".db"}:
            files.append(path)
        elif suffix == ".csv" and any(
            hint in path.name.lower() for hint in SETTLED_SOURCE_HINTS
        ):
            files.append(path)
    return sorted(files, key=lambda item: str(item).lower())


def build(data_dir: Path, output: Path, replace_derived: bool = False) -> dict[str, Any]:
    data_dir = data_dir.resolve()
    output = output.resolve()
    if output.exists() and not replace_derived:
        raise FileExistsError(
            f"Derived output already exists: {output}. Use --replace-derived explicitly."
        )
    sources = source_files(data_dir)
    hashes_before = {str(path): sha256_file(path) for path in sources}
    records: dict[str, dict[str, Any]] = {}
    scanned = 0
    for path in sources:
        relative = path.relative_to(data_dir).as_posix()
        if path.suffix.lower() == ".csv":
            for row in _csv_rows(path):
                scanned += 1
                transformed = transform_row(row, relative)
                if transformed:
                    records[transformed["record_id"]] = transformed
        else:
            for table, row in _sqlite_rows(path):
                scanned += 1
                transformed = transform_row(row, f"{relative}::{table}")
                if transformed:
                    records[transformed["record_id"]] = transformed
    hashes_after = {str(path): sha256_file(path) for path in sources}
    if hashes_before != hashes_after:
        raise RuntimeError("A source history file changed during read-only extraction.")
    ordered = sorted(
        records.values(),
        key=lambda row: (row["timestamp"], row["record_id"]),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    fields = [
        "timestamp", "source", "record_id", "market",
        "current_probability", "dixon_coles_probability",
        "market_probability", "market_probability_method", "target",
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
