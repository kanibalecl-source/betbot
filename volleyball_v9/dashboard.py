"""Read-only presentation snapshot for the volleyball web panel."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .storage import VolleyballStorage


DASHBOARD_SCHEMA_VERSION = "betbot.volleyball.dashboard.v10.1"


def _empty_snapshot(status: str = "WAITING_FOR_DATABASE") -> dict[str, Any]:
    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "available": False,
        "status": status,
        "health": {},
        "coverage": {
            "games_total": 0,
            "games_finished": 0,
            "games_upcoming": 0,
            "games_with_odds": 0,
            "odds_quotes": 0,
            "identity_acceptance_rate": 0.0,
            "model_candidates": 0,
            "model_validations": 0,
            "live_shadow_reports": 0,
            "live_registry_integrity": True,
        },
        "games": [],
        "picks": [],
        "candidate_rows": 0,
        "candidate_minimum_rows": 100,
        "active_model_id": "BASELINE",
        "governor_status": "WAITING_REPRODUCIBLE_CANDIDATE",
        "governor_enabled": False,
        "shadow_only": True,
        "real_execution_allowed": False,
        "football_data_modified": False,
    }


def _row_dict(row: Any) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def load_volleyball_dashboard(
    root: str | Path | None = None,
    *,
    game_limit: int = 100,
    pick_limit: int = 100,
) -> dict[str, Any]:
    """Return a bounded, secret-free snapshot without mutating the database."""
    storage = VolleyballStorage(root)
    if not storage.db_path.exists():
        return _empty_snapshot()

    try:
        coverage = storage.coverage_summary()
        games = sorted(
            storage.load_games(),
            key=lambda game: (game.scheduled_at, game.game_id),
            reverse=True,
        )[: max(1, int(game_limit))]
        picks = [
            _row_dict(row)
            for row in [*storage.open_picks(), *storage.closed_picks()]
        ]
        picks.sort(
            key=lambda row: (
                str(row.get("generated_at", "")),
                str(row.get("pick_key", "")),
            ),
            reverse=True,
        )
        health_raw = storage.state("last_health")
        health = json.loads(health_raw) if health_raw else {}
        if not isinstance(health, dict):
            health = {}
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
            "home_sets": game.home_sets,
            "away_sets": game.away_sets,
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
        "picks": picks[: max(1, int(pick_limit))],
        "candidate_rows": int(
            health.get("candidate_dataset_rows", coverage.get("games_finished", 0))
        ),
        "candidate_minimum_rows": int(
            health.get("candidate_minimum_rows", 100)
        ),
        "active_model_id": str(
            health.get("active_shadow_model_id", storage.active_shadow_model_id())
        ),
        "governor_status": str(
            health.get(
                "autonomous_governor_status",
                "WAITING_REPRODUCIBLE_CANDIDATE",
            )
        ),
        "governor_enabled": bool(
            health.get("autonomous_governor_enabled", False)
        ),
        "shadow_only": bool(health.get("shadow_only", True)),
        "real_execution_allowed": bool(
            health.get("real_execution_allowed", False)
        ),
        "football_data_modified": bool(
            health.get("football_data_modified", False)
        ),
    }

