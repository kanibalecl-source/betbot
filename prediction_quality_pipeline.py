"""Prediction-time evidence ledger and conservative portfolio selection.

The module is deliberately downstream from probability estimation.  It never
changes model probabilities and never promotes a model.  It freezes the exact
information available at decision time and can only abstain from publishing a
recommendation.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from storage_paths import get_data_dir


FEATURE_FIELDS = (
    "home_xg", "away_xg", "odds_observed_at", "lineup_available",
    "injuries_available", "home_rest_days", "away_rest_days",
    "home_form_home", "away_form_away", "coach_change",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _present(value: Any) -> bool:
    return str(value).strip().lower() not in {"", "none", "nan", "null", "unknown"}


def _number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _first(source: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        value = source.get(name)
        if _present(value):
            return value
    return None


def build_feature_snapshot(
    match: Mapping[str, Any],
    odds: Mapping[str, Any],
    *,
    home_xg: Any,
    away_xg: Any,
    probability: Any,
    league: Any,
) -> dict[str, Any]:
    """Return explicit feature availability without inventing missing values."""
    values = {
        "home_xg": home_xg,
        "away_xg": away_xg,
        "odds_observed_at": _first(odds, "observed_at", "odds_observed_at", "updated_at"),
        "lineup_available": _first(match, "lineup_available", "lineups_available", "lineup_confirmed"),
        "injuries_available": _first(match, "injuries_available", "injury_data_available"),
        "home_rest_days": _first(match, "home_rest_days", "rest_days_home"),
        "away_rest_days": _first(match, "away_rest_days", "rest_days_away"),
        "home_form_home": _first(match, "home_form_home", "home_home_form"),
        "away_form_away": _first(match, "away_form_away", "away_away_form"),
        "coach_change": _first(match, "coach_change", "manager_change"),
    }
    core = (home_xg, away_xg, probability, league, values["odds_observed_at"])
    context = tuple(values[name] for name in FEATURE_FIELDS[3:])
    core_score = sum(_present(value) for value in core) / len(core)
    context_score = sum(_present(value) for value in context) / len(context)
    completeness = 0.75 * core_score + 0.25 * context_score
    missing = [name for name, value in values.items() if not _present(value)]
    return {
        **values,
        "feature_completeness": round(completeness, 6),
        "data_quality": "HIGH" if completeness >= 0.85 else "MEDIUM" if completeness >= 0.65 else "LOW",
        "missing_features": missing,
        "missing_features_json": json.dumps(missing, ensure_ascii=False),
        "missing_features_imputed": False,
    }


def _database(data_dir: str | Path | None = None) -> Path:
    root = Path(data_dir or get_data_dir()).resolve() / "quality_retraining"
    root.mkdir(parents=True, exist_ok=True)
    return root / "prediction_evidence.sqlite3"


def _connect(data_dir: str | Path | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(_database(data_dir), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=30000")
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS prediction_ledger (
        snapshot_id TEXT PRIMARY KEY,
        recorded_at TEXT NOT NULL,
        fixture_id TEXT,
        kickoff TEXT,
        league TEXT,
        match_name TEXT,
        market TEXT NOT NULL,
        bookmaker TEXT,
        odds_taken REAL,
        odds_observed_at TEXT,
        strategy_version TEXT,
        model_version TEXT,
        probability REAL,
        edge REAL,
        ev REAL,
        feature_completeness REAL,
        raw_json TEXT NOT NULL,
        raw_sha256 TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_prediction_ledger_fixture
        ON prediction_ledger(fixture_id, market);
    CREATE TABLE IF NOT EXISTS closing_odds_ledger (
        closing_key TEXT PRIMARY KEY,
        snapshot_id TEXT,
        recorded_at TEXT NOT NULL,
        fixture_id TEXT,
        market TEXT,
        bookmaker TEXT,
        odds_taken REAL,
        closing_odds REAL NOT NULL,
        clv REAL,
        source TEXT,
        raw_json TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_closing_odds_fixture
        ON closing_odds_ledger(fixture_id, market, recorded_at);
    """)
    connection.commit()
    return connection


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def prediction_snapshot_id(pick: Mapping[str, Any]) -> str:
    identity = "|".join((
        str(pick.get("fixture_id") or pick.get("match") or ""),
        str(pick.get("match_date") or ""),
        str(pick.get("market") or ""),
        str(pick.get("bookmaker") or ""),
        str(pick.get("strategy_version") or ""),
    ))
    return hashlib.sha256(identity.encode("utf-8", errors="ignore")).hexdigest()


def record_prediction_snapshot(
    pick: Mapping[str, Any], data_dir: str | Path | None = None
) -> dict[str, Any]:
    """Insert once. Existing evidence is never updated or deleted."""
    payload = dict(pick)
    snapshot_id = prediction_snapshot_id(payload)
    raw = _canonical(payload)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    connection = _connect(data_dir)
    try:
        cursor = connection.execute("""
            INSERT OR IGNORE INTO prediction_ledger (
                snapshot_id, recorded_at, fixture_id, kickoff, league, match_name,
                market, bookmaker, odds_taken, odds_observed_at, strategy_version,
                model_version, probability, edge, ev, feature_completeness,
                raw_json, raw_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot_id, str(payload.get("decision_at") or _now()),
            str(payload.get("fixture_id") or ""), str(payload.get("match_date") or ""),
            str(payload.get("league") or ""), str(payload.get("match") or payload.get("mecz") or ""),
            str(payload.get("market") or ""), str(payload.get("bookmaker") or ""),
            _number(payload.get("odds") or payload.get("kurs_buk")),
            str(payload.get("odds_observed_at") or ""),
            str(payload.get("strategy_version") or ""), str(payload.get("model_version") or ""),
            _number(payload.get("prawd_final") or payload.get("probability")),
            _number(payload.get("edge")), _number(payload.get("ev")),
            _number(payload.get("feature_completeness") or payload.get("quality_data_completeness")),
            raw, digest,
        ))
        connection.commit()
        return {
            "status": "RECORDED" if cursor.rowcount else "ALREADY_RECORDED",
            "snapshot_id": snapshot_id,
            "immutable": True,
        }
    finally:
        connection.close()


def record_closing_odds(
    observation: Mapping[str, Any], data_dir: str | Path | None = None
) -> dict[str, Any]:
    closing = _number(observation.get("closing_odds"))
    taken = _number(observation.get("odds_taken") or observation.get("odds"))
    if closing is None or closing <= 1.0:
        return {"status": "INVALID_CLOSING_ODDS"}
    payload = dict(observation)
    recorded_at = str(payload.get("recorded_at") or _now())
    raw_key = "|".join((
        str(payload.get("snapshot_id") or ""), str(payload.get("fixture_id") or ""),
        str(payload.get("market") or ""), recorded_at, str(closing),
    ))
    closing_key = hashlib.sha256(raw_key.encode("utf-8", errors="ignore")).hexdigest()
    clv = taken / closing - 1.0 if taken is not None and taken > 1.0 else None
    connection = _connect(data_dir)
    try:
        cursor = connection.execute("""
            INSERT OR IGNORE INTO closing_odds_ledger (
                closing_key, snapshot_id, recorded_at, fixture_id, market,
                bookmaker, odds_taken, closing_odds, clv, source, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            closing_key, str(payload.get("snapshot_id") or ""), recorded_at,
            str(payload.get("fixture_id") or ""), str(payload.get("market") or ""),
            str(payload.get("bookmaker") or ""), taken, closing, clv,
            str(payload.get("source") or "closing_odds_pipeline"), _canonical(payload),
        ))
        connection.commit()
        return {
            "status": "RECORDED" if cursor.rowcount else "ALREADY_RECORDED",
            "closing_key": closing_key,
            "clv": round(clv, 8) if clv is not None else None,
        }
    finally:
        connection.close()


def select_portfolio(
    rows: Iterable[Mapping[str, Any]],
    *,
    maximum_daily: int | None = None,
    data_dir: str | Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Keep the best independent recommendations across all daily bot cycles."""
    limit = maximum_daily if maximum_daily is not None else int(
        os.getenv("BETBOT_MAX_DAILY_RECOMMENDATIONS", "12")
    )
    limit = max(1, min(100, int(limit)))
    ordered = sorted(
        (dict(row) for row in rows),
        key=lambda row: (
            -float(_number(row.get("ai_pick_score")) or 0.0),
            -float(_number(row.get("ev")) or 0.0),
            -float(_number(row.get("edge")) or 0.0),
            str(row.get("fixture_id") or row.get("match") or ""),
        ),
    )
    accepted: list[dict[str, Any]] = []
    fixtures: set[str] = set()
    team_days: set[tuple[str, str]] = set()
    existing_snapshots: set[str] = set()
    daily_existing = 0
    try:
        connection = _connect(data_dir)
        today = datetime.now(timezone.utc).date().isoformat()
        existing = connection.execute(
            "SELECT snapshot_id, fixture_id, raw_json FROM prediction_ledger "
            "WHERE substr(recorded_at, 1, 10)=?",
            (today,),
        ).fetchall()
        connection.close()
        for item in existing:
            existing_snapshots.add(str(item["snapshot_id"]))
            fixture = str(item["fixture_id"] or "").lower()
            if fixture:
                fixtures.add(fixture)
            try:
                raw = json.loads(item["raw_json"] or "{}")
            except Exception:
                raw = {}
            day = str(raw.get("match_date") or raw.get("decision_at") or "")[:10]
            for team in {
                str(raw.get("home_team") or raw.get("home") or "").strip().lower(),
                str(raw.get("away_team") or raw.get("away") or "").strip().lower(),
            } - {""}:
                if day:
                    team_days.add((team, day))
        daily_existing = len(fixtures) if fixtures else len(existing_snapshots)
    except Exception:
        # Selection remains deterministic inside the current cycle if the
        # evidence database is temporarily unavailable.
        existing_snapshots = set()
    stats = {
        "same_fixture": 0, "correlated_team_day": 0, "daily_limit": 0,
        "already_published": 0, "existing_daily": daily_existing,
    }
    new_count = 0
    for row in ordered:
        snapshot_id = prediction_snapshot_id(row)
        if snapshot_id in existing_snapshots:
            row["portfolio_selection_status"] = "ALREADY_PUBLISHED"
            row["portfolio_daily_limit"] = limit
            accepted.append(row)
            stats["already_published"] += 1
            continue
        fixture = str(row.get("fixture_id") or row.get("match") or "").lower()
        if fixture and fixture in fixtures:
            stats["same_fixture"] += 1
            continue
        day = str(row.get("match_date") or row.get("decision_at") or "")[:10]
        teams = {
            str(row.get("home_team") or row.get("home") or "").strip().lower(),
            str(row.get("away_team") or row.get("away") or "").strip().lower(),
        } - {""}
        correlations = {(team, day) for team in teams if day}
        if correlations & team_days:
            stats["correlated_team_day"] += 1
            continue
        if daily_existing + new_count >= limit:
            stats["daily_limit"] += 1
            continue
        row["portfolio_selection_status"] = "ACCEPTED"
        row["portfolio_daily_limit"] = limit
        accepted.append(row)
        new_count += 1
        if fixture:
            fixtures.add(fixture)
        team_days.update(correlations)
    return accepted, stats
