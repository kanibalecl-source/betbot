"""Read-only presentation snapshot for the basketball shadow panel."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .storage import BasketballStorage


DASHBOARD_SCHEMA_VERSION = "betbot.basketball.dashboard.v20.3"


def _empty_snapshot(status: str = "WAITING_FOR_DATABASE") -> dict[str, Any]:
    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "available": False,
        "status": status,
        "health": {},
        "coverage": {
            "games_total": 0,
            "games_quality_settled": 0,
            "games_with_odds": 0,
            "odds_quotes": 0,
            "settlements_total": 0,
            "quarantined": 0,
            "provider_calls": 0,
            "provider_success": 0,
            "provider_failed": 0,
            "provider_failure_categories": {},
            "provider_quota": {
                "limit": None,
                "remaining": None,
                "retry_after_seconds": None,
            },
        },
        "games": [],
        "odds": [],
        "shadow_only": True,
        "collection_autonomous": True,
        "settlement_autonomous": True,
        "training_admission_allowed": False,
        "model_candidate_creation_allowed": False,
        "automatic_model_promotion_allowed": False,
        "real_execution_allowed": False,
        "database_integrity": True,
    }


def _storage(root: str | Path | None) -> BasketballStorage:
    if root is None:
        return BasketballStorage()
    path = Path(root)
    if path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
        return BasketballStorage(path)
    return BasketballStorage(path / "basketball_shadow.sqlite3")


def _latest_odds(db_path: Path, limit: int) -> list[dict[str, Any]]:
    """Load a bounded odds view through a strictly read-only SQLite handle."""
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=10)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                o.game_id,
                g.league_name,
                g.home_team,
                g.away_team,
                o.bookmaker,
                o.market,
                o.outcome,
                o.line,
                o.odds,
                o.observed_at
            FROM basketball_odds AS o
            JOIN basketball_games AS g ON g.game_id = o.game_id
            WHERE o.rowid IN (
                SELECT MAX(rowid)
                FROM basketball_odds
                GROUP BY
                    game_id, bookmaker_id, market, outcome,
                    COALESCE(CAST(line AS TEXT), '')
            )
            ORDER BY o.observed_at DESC, o.game_id, o.bookmaker, o.market
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
    return [{key: row[key] for key in row.keys()} for row in rows]


def load_basketball_dashboard(
    root: str | Path | None = None,
    *,
    game_limit: int = 100,
    odds_limit: int = 100,
) -> dict[str, Any]:
    """Return a bounded, secret-free snapshot without changing model state."""
    storage = _storage(root)
    if not storage.db_path.exists():
        return _empty_snapshot()

    try:
        coverage = storage.coverage_summary()
        games = sorted(
            storage.load_games(),
            key=lambda game: (game.scheduled_at, game.game_id),
            reverse=True,
        )[: max(1, int(game_limit))]
        health_raw = storage.state("last_health")
        health = json.loads(health_raw) if health_raw else {}
        if not isinstance(health, dict):
            health = {}
        odds = _latest_odds(storage.db_path, odds_limit)
        integrity = storage.database_integrity()
    except Exception as exc:
        snapshot = _empty_snapshot("READ_ERROR")
        snapshot["error_type"] = type(exc).__name__
        return snapshot

    game_rows = [
        {
            "game_id": game.game_id,
            "scheduled_at": game.scheduled_at,
            "status": game.status,
            "league_name": game.league_name,
            "country": game.country,
            "season": game.season,
            "home_team": game.home_team,
            "away_team": game.away_team,
            "home_score": game.home_score,
            "away_score": game.away_score,
            "overtime": game.overtime,
            "finished": game.finished,
        }
        for game in games
    ]

    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "available": True,
        "status": str(health.get("status", "WAITING_FIRST_CYCLE")),
        "health": health,
        "coverage": coverage,
        "games": game_rows,
        "odds": odds,
        "shadow_only": True,
        "collection_autonomous": bool(
            health.get("collection_autonomous", True)
        ),
        "settlement_autonomous": bool(
            health.get("settlement_autonomous", True)
        ),
        "training_admission_allowed": bool(
            health.get("training_admission_allowed", False)
        ),
        "model_candidate_creation_allowed": bool(
            health.get("model_candidate_creation_allowed", False)
        ),
        "automatic_model_promotion_allowed": bool(
            health.get("automatic_model_promotion_allowed", False)
        ),
        "real_execution_allowed": bool(
            health.get("real_execution_allowed", False)
        ),
        "database_integrity": bool(
            health.get("database_integrity", integrity)
        ),
    }
