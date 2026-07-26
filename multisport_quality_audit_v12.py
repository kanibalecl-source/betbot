"""Read-only autonomous quality audit for football, volleyball and handball."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from multisport_quality_v12 import (
    SCHEMA_VERSION,
    audit_sport_isolation,
    calibration_report,
    grade_leagues,
    odds_snapshot_stage,
    policy_for,
)
from storage_paths import get_data_dir


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _rows(connection: sqlite3.Connection, query: str) -> list[dict[str, Any]]:
    try:
        return [dict(row) for row in connection.execute(query).fetchall()]
    except sqlite3.DatabaseError:
        return []


def _sport_database(root: Path, sport: str) -> Path:
    filename = (
        "volleyball_shadow.sqlite3"
        if sport == "volleyball"
        else "handball_shadow.sqlite3"
    )
    return root / sport / filename


def _audit_shadow_sport(root: Path, sport: str) -> dict[str, Any]:
    path = _sport_database(root, sport)
    policy = policy_for(sport)
    if not path.exists():
        return {
            "sport": sport,
            "status": "WAITING_DATABASE",
            "policy": policy.__dict__,
            "promotion_allowed": False,
        }
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        games = _rows(
            connection,
            """
            SELECT sport, game_id, scheduled_at, league_id, home_team_id,
                   away_team_id, status
            FROM games
            """,
        )
        picks = _rows(
            connection,
            """
            SELECT p.sport, p.game_id AS fixture_id, g.scheduled_at,
                   g.league_id, g.home_team_id, g.away_team_id,
                   p.status, p.result, p.model_probability,
                   p.bookmaker_odds, p.created_at,
                   c.closing_fair_odds AS closing_odds
            FROM shadow_picks p
            JOIN games g ON g.game_id=p.game_id
            LEFT JOIN pick_clv c ON c.pick_key=p.pick_key
            """,
        )
        quotes = _rows(
            connection,
            """
            SELECT o.game_id, o.observed_at, g.scheduled_at
            FROM odds_snapshots o JOIN games g ON g.game_id=o.game_id
            """,
        )
    finally:
        connection.close()

    for row in picks:
        row["settled"] = str(row.get("status", "")).upper() == "CLOSED"
    league_grades = grade_leagues(picks, sport=sport)
    grade_ab = sum(
        int(item["samples"])
        for item in league_grades.values()
        if item["grade"] in {"A", "B"}
    )
    settled = [
        row
        for row in picks
        if row["settled"] and str(row.get("result", "")).upper() in {"WON", "LOST"}
    ]
    probabilities = [float(row["model_probability"]) for row in settled]
    targets = [
        1 if str(row.get("result", "")).upper() == "WON" else 0
        for row in settled
    ]
    stages: dict[str, int] = {}
    for quote in quotes:
        stage = odds_snapshot_stage(quote.get("scheduled_at"), quote.get("observed_at"))
        stages[stage] = stages.get(stage, 0) + 1
    closing_games = {
        str(row["game_id"])
        for row in quotes
        if odds_snapshot_stage(row.get("scheduled_at"), row.get("observed_at"))
        == "CLOSING"
    }
    fixture_games = {str(row.get("game_id")) for row in games}
    settlement_coverage = len(settled) / len(picks) if picks else 0.0
    closing_coverage = len(closing_games) / len(fixture_games) if fixture_games else 0.0
    isolation = audit_sport_isolation({sport: games})
    calibration = calibration_report(probabilities, targets)
    return {
        "sport": sport,
        "status": "HEALTHY" if isolation["isolated"] else "FAIL_CLOSED",
        "policy": policy.__dict__,
        "games": len(games),
        "picks": len(picks),
        "settled_quality_rows": len(settled),
        "settlement_coverage": round(settlement_coverage, 8),
        "closing_odds_coverage": round(closing_coverage, 8),
        "odds_snapshot_stages": stages,
        "league_grades": league_grades,
        "grade_ab_share": round(grade_ab / len(picks), 8) if picks else 0.0,
        "calibration": calibration,
        "sport_isolation": isolation,
        "promotion_allowed": False,
        "promotion_note": "Final promotion remains owned by sport walk-forward and live-shadow governor.",
        "source_database_modified": False,
    }


class MultisportQualityAuditV12:
    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.root = Path(data_dir or get_data_dir()).resolve()
        self.report_path = self.root / "quality_retraining" / "multisport_v12_audit.json"

    def run(self) -> dict[str, Any]:
        football_guardian = self.root / "quality_retraining" / "data_quality_guardian.json"
        try:
            football = json.loads(football_guardian.read_text(encoding="utf-8"))
        except Exception:
            football = {"status": "WAITING_GUARDIAN"}
        sports = {
            "football": {
                "sport": "football",
                "status": str(football.get("status", "WAITING_GUARDIAN")),
                "policy": policy_for("football").__dict__,
                "guardian": football,
                "promotion_allowed": False,
                "promotion_note": "Final promotion remains owned by Champion-Challenger governor.",
                "v12_independent_challenger": {
                    "enabled": True,
                    "bookmaker_used_as_model_input": False,
                    "market_used_only_as_benchmark": True,
                    "activation": "shadow_then_walk_forward_then_live_shadow",
                },
            },
            "volleyball": _audit_shadow_sport(self.root, "volleyball"),
            "handball": _audit_shadow_sport(self.root, "handball"),
        }
        payload = {
            "schema_version": SCHEMA_VERSION,
            "updated_at": _now(),
            "status": (
                "HEALTHY"
                if all(item.get("status") != "FAIL_CLOSED" for item in sports.values())
                else "FAIL_CLOSED"
            ),
            "sports": sports,
            "source_history_modified": False,
            "active_models_modified": False,
            "financial_execution_modified": False,
        }
        _atomic(self.report_path, payload)
        return payload
