"""Forward-only Champion-Challenger observatory and closing-odds snapshots."""
from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from quality_upgrade_engine import assess_quality
from storage_paths import get_data_dir


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return dict(value) if isinstance(value, Mapping) else {}
    except Exception:
        return {}


def _first(row: Mapping[str, Any], names: tuple[str, ...], default: Any = "") -> Any:
    for name in names:
        value = row.get(name)
        if value not in (None, "", "nan", "None", "null"):
            return value
    return default


def _float(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _database(data_dir: str | Path | None = None) -> Path:
    root = Path(data_dir or get_data_dir()).resolve() / "quality_retraining"
    root.mkdir(parents=True, exist_ok=True)
    return root / "quality_observatory.sqlite3"


def _connect(data_dir: str | Path | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(_database(data_dir), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=30000")
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS live_shadow_predictions (
        prediction_key TEXT PRIMARY KEY,
        recorded_at TEXT NOT NULL,
        candidate_id TEXT NOT NULL,
        fixture_id TEXT,
        kickoff TEXT,
        league TEXT,
        match_name TEXT,
        market TEXT NOT NULL,
        odds_taken REAL,
        champion_probability REAL NOT NULL,
        challenger_probability REAL NOT NULL,
        target INTEGER,
        settled_at TEXT,
        closing_odds REAL,
        champion_brier REAL,
        challenger_brier REAL,
        raw_json TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_live_shadow_unsettled
        ON live_shadow_predictions(target, fixture_id);
    CREATE TABLE IF NOT EXISTS odds_snapshots (
        snapshot_key TEXT PRIMARY KEY,
        recorded_at TEXT NOT NULL,
        fixture_id TEXT,
        match_name TEXT,
        kickoff TEXT,
        market TEXT,
        bucket TEXT NOT NULL,
        odds REAL NOT NULL,
        bookmaker TEXT
    );
    """)
    connection.commit()
    return connection


def _candidate_paths(data_dir: str | Path | None = None) -> tuple[Path, Path]:
    root = Path(data_dir or get_data_dir()).resolve()
    active = Path(os.getenv("BETBOT_QUALITY_STATE", root / "quality_shadow_state.json"))
    candidate = Path(os.getenv(
        "BETBOT_QUALITY_CANDIDATE",
        root / "quality_retraining" / "quality_shadow_state.candidate.latest.json",
    ))
    return active, candidate


def _identity(raw: Mapping[str, Any], output: Mapping[str, Any]) -> dict[str, str]:
    home = str(_first(raw, ("home", "home_team", "gospodarze")))
    away = str(_first(raw, ("away", "away_team", "goscie")))
    match_name = str(_first(
        raw, ("match", "mecz", "match_name"), f"{home} vs {away}".strip()
    ))
    return {
        "fixture_id": str(_first(raw, ("fixture_id", "event_id", "id"))),
        "kickoff": str(_first(raw, ("match_date", "kickoff", "date", "commence_time"))),
        "league": str(_first(raw, ("league", "liga", "competition"), "UNKNOWN")),
        "match_name": match_name,
        "market": str(_first(output, ("market", "signal"), _first(raw, ("market", "typ", "signal")))).upper(),
    }


def _hours_to_kickoff(value: str) -> float | None:
    if not value:
        return None
    try:
        kickoff = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        return (kickoff.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds() / 3600
    except Exception:
        return None


def _snapshot_buckets(hours: float | None) -> list[str]:
    buckets = ["LATEST_PREMATCH"]
    if hours is None:
        return buckets
    if 18 <= hours <= 30:
        buckets.append("T24H")
    if 4 <= hours <= 8:
        buckets.append("T6H")
    if 0 <= hours <= 2:
        buckets.append("T1H")
    return buckets


def record_live_shadow(
    raw: Mapping[str, Any],
    current_output: Mapping[str, Any],
    data_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Record frozen future predictions; never alter current_output or active state."""
    active_path, candidate_path = _candidate_paths(data_dir)
    candidate = _read_json(candidate_path)
    if not candidate:
        return {"status": "NO_CANDIDATE"}
    active = _read_json(active_path)
    identity = _identity(raw, current_output)
    if not identity["market"] or not (identity["fixture_id"] or identity["match_name"]):
        return {"status": "MISSING_IDENTITY"}
    champion = assess_quality(raw, current_output, state=active or {}).calibrated_probability
    challenger = assess_quality(raw, current_output, state=candidate).calibrated_probability
    candidate_id = str(candidate.get("candidate_path") or candidate.get("created_at") or candidate_path.name)
    raw_key = "|".join((
        candidate_id,
        identity["fixture_id"] or identity["match_name"].lower(),
        identity["kickoff"],
        identity["market"],
    ))
    prediction_key = hashlib.sha256(raw_key.encode("utf-8", errors="ignore")).hexdigest()
    odds = _float(_first(current_output, ("odds", "bookmaker_odds"), _first(raw, ("odds", "kurs_buk"))))
    connection = _connect(data_dir)
    try:
        cursor = connection.execute("""
            INSERT OR IGNORE INTO live_shadow_predictions (
                prediction_key, recorded_at, candidate_id, fixture_id, kickoff,
                league, match_name, market, odds_taken, champion_probability,
                challenger_probability, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prediction_key, _now(), candidate_id, identity["fixture_id"], identity["kickoff"],
            identity["league"], identity["match_name"], identity["market"], odds,
            champion, challenger, json.dumps(dict(raw), ensure_ascii=False, default=str),
        ))
        if odds is not None and odds > 1.0:
            hours = _hours_to_kickoff(identity["kickoff"])
            for bucket in _snapshot_buckets(hours):
                snapshot_raw = "|".join((
                    identity["fixture_id"] or identity["match_name"].lower(),
                    identity["market"], bucket,
                ))
                snapshot_key = hashlib.sha256(snapshot_raw.encode("utf-8")).hexdigest()
                if bucket == "LATEST_PREMATCH":
                    connection.execute("""
                        INSERT INTO odds_snapshots (
                            snapshot_key, recorded_at, fixture_id, match_name, kickoff,
                            market, bucket, odds, bookmaker
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(snapshot_key) DO UPDATE SET
                            recorded_at=excluded.recorded_at, odds=excluded.odds,
                            bookmaker=excluded.bookmaker
                    """, (
                        snapshot_key, _now(), identity["fixture_id"], identity["match_name"],
                        identity["kickoff"], identity["market"], bucket, odds,
                        str(_first(raw, ("bookmaker", "bukmacher"))),
                    ))
                else:
                    connection.execute("""
                        INSERT OR IGNORE INTO odds_snapshots (
                            snapshot_key, recorded_at, fixture_id, match_name, kickoff,
                            market, bucket, odds, bookmaker
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        snapshot_key, _now(), identity["fixture_id"], identity["match_name"],
                        identity["kickoff"], identity["market"], bucket, odds,
                        str(_first(raw, ("bookmaker", "bukmacher"))),
                    ))
        connection.commit()
        return {
            "status": "RECORDED" if cursor.rowcount else "ALREADY_RECORDED",
            "prediction_key": prediction_key,
            "active_model_modified": False,
        }
    finally:
        connection.close()


def reconcile_live_shadow(
    data_dir: str | Path | None = None,
    limit: int = 250,
) -> dict[str, int]:
    """Settle recorded shadow predictions from finished fixtures."""
    try:
        from result_updater_unified import evaluate_market, fetch_result
    except Exception:
        return {"checked": 0, "settled": 0}
    connection = _connect(data_dir)
    rows = connection.execute("""
        SELECT * FROM live_shadow_predictions
        WHERE target IS NULL AND fixture_id IS NOT NULL AND fixture_id != ''
        ORDER BY recorded_at ASC LIMIT ?
    """, (max(1, int(limit)),)).fetchall()
    results: dict[str, Any] = {}
    checked = settled = 0
    try:
        for row in rows:
            checked += 1
            fixture_id = str(row["fixture_id"])
            if fixture_id not in results:
                results[fixture_id] = fetch_result(fixture_id)
            result = results[fixture_id]
            if not result:
                continue
            won = evaluate_market(row["market"], result["home_goals"], result["away_goals"])
            if won is None:
                continue
            target = int(bool(won))
            latest = connection.execute("""
                SELECT odds FROM odds_snapshots
                WHERE fixture_id=? AND market=? AND bucket='LATEST_PREMATCH'
                ORDER BY recorded_at DESC LIMIT 1
            """, (fixture_id, row["market"])).fetchone()
            closing = float(latest["odds"]) if latest else None
            champion_brier = (float(row["champion_probability"]) - target) ** 2
            challenger_brier = (float(row["challenger_probability"]) - target) ** 2
            connection.execute("""
                UPDATE live_shadow_predictions SET
                    target=?, settled_at=?, closing_odds=?, champion_brier=?,
                    challenger_brier=? WHERE prediction_key=? AND target IS NULL
            """, (
                target, _now(), closing, champion_brier, challenger_brier,
                row["prediction_key"],
            ))
            settled += 1
        connection.commit()
        return {"checked": checked, "settled": settled}
    finally:
        connection.close()


def live_shadow_report(data_dir: str | Path | None = None) -> dict[str, Any]:
    _, candidate_path = _candidate_paths(data_dir)
    candidate = _read_json(candidate_path)
    candidate_id = str(
        candidate.get("candidate_path") or candidate.get("created_at") or candidate_path.name
    )
    connection = _connect(data_dir)
    try:
        rows = connection.execute("""
            SELECT * FROM live_shadow_predictions
            WHERE target IS NOT NULL AND candidate_id=?
            ORDER BY settled_at ASC
        """, (candidate_id,)).fetchall()
        pending = connection.execute(
            "SELECT COUNT(*) AS n FROM live_shadow_predictions "
            "WHERE target IS NULL AND candidate_id=?",
            (candidate_id,),
        ).fetchone()["n"]
    finally:
        connection.close()
    if not rows:
        return {
            "status": "WAITING_FOR_FUTURE_SETTLEMENTS",
            "settled_samples": 0,
            "pending_samples": int(pending),
            "candidate_id": candidate_id,
            "automatic_promotion": False,
        }

    def metrics(field: str) -> dict[str, float]:
        probabilities = [float(row[field]) for row in rows]
        targets = [int(row["target"]) for row in rows]
        brier = sum((p - y) ** 2 for p, y in zip(probabilities, targets)) / len(rows)
        loss = -sum(
            y * math.log(max(1e-8, p)) + (1-y) * math.log(max(1e-8, 1-p))
            for p, y in zip(probabilities, targets)
        ) / len(rows)
        return {"brier_score": round(brier, 8), "log_loss": round(loss, 8)}

    champion = metrics("champion_probability")
    challenger = metrics("challenger_probability")
    brier_gain = champion["brier_score"] - challenger["brier_score"]
    log_gain = champion["log_loss"] - challenger["log_loss"]
    minimum = int(os.getenv("BETBOT_LIVE_SHADOW_MIN_SAMPLES", "300"))
    positive = len(rows) >= minimum and brier_gain > 0.0002 and log_gain > 0.0002
    return {
        "status": "POSITIVE_LIVE_SHADOW_MANUAL_APPROVAL" if positive else "COLLECTING_OR_REVIEW",
        "settled_samples": len(rows),
        "pending_samples": int(pending),
        "candidate_id": candidate_id,
        "minimum_samples": minimum,
        "champion": champion,
        "challenger": challenger,
        "brier_improvement": round(brier_gain, 8),
        "log_loss_improvement": round(log_gain, 8),
        "automatic_promotion": False,
        "manual_approval_required": True,
    }
