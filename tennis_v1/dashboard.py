from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from storage_paths import DATA_DIR

from .storage import TennisStorage


DASHBOARD_SCHEMA_VERSION = "betbot.tennis.dashboard.v1.0"


def _empty(status: str = "WAITING_FOR_DATABASE") -> dict[str, Any]:
    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "available": False,
        "status": status,
        "health": {},
        "coverage": {
            "matches_total": 0,
            "matches_finished_admitted": 0,
            "matches_with_consensus_odds": 0,
            "odds_quotes": 0,
            "surface_rows": {},
            "model_candidates": 0,
            "model_validations": 0,
            "quarantined": 0,
        },
        "matches": [],
        "picks": [],
        "candidate_rows": 0,
        "candidate_minimum_rows": 1500,
        "active_model_id": "BASELINE",
        "governor_status": "WAITING_MINIMUM_SAMPLE",
        "governor_enabled": False,
        "shadow_only": True,
        "real_execution_allowed": False,
    }


def _row(row: Any) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def load_tennis_dashboard(
    root: str | Path | None = None,
    *,
    match_limit: int = 100,
    pick_limit: int = 100,
) -> dict[str, Any]:
    data_root = Path(root) if root is not None else Path(DATA_DIR) / "tennis"
    if not (data_root / "tennis_shadow.sqlite3").exists():
        return _empty()
    try:
        storage = TennisStorage(data_root)
        coverage = storage.coverage_summary()
        matches = sorted(
            storage.load_matches(),
            key=lambda item: (item.scheduled_at, item.event_id),
            reverse=True,
        )[: max(1, int(match_limit))]
        picks = [_row(row) for row in [*storage.open_picks(), *storage.closed_picks()]]
        picks.sort(
            key=lambda item: (
                str(item.get("created_at", "")),
                str(item.get("pick_key", "")),
            ),
            reverse=True,
        )
        health_raw = storage.state("last_health")
        health = json.loads(health_raw) if health_raw else {}
        if not isinstance(health, dict):
            health = {}
        active_model, _weights = storage.active_shadow_model()
    except Exception as exc:
        snapshot = _empty("READ_ERROR")
        snapshot["error_type"] = type(exc).__name__
        return snapshot
    rows = [
        {
            "event_id": match.event_id,
            "scheduled_at": match.scheduled_at,
            "status": match.status,
            "tour": match.tour,
            "competition_name": match.competition_name,
            "surface": match.surface,
            "player1_name": match.player1_name,
            "player2_name": match.player2_name,
            "score": (
                f"{match.player1_sets}:{match.player2_sets}"
                if match.player1_sets is not None and match.player2_sets is not None
                else "-"
            ),
            "finished": match.finished,
        }
        for match in matches
    ]
    validation = health.get("validation", {})
    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "available": True,
        "status": str(health.get("status", "WAITING_FIRST_CYCLE")),
        "health": health,
        "coverage": coverage,
        "matches": rows,
        "picks": picks[: max(1, int(pick_limit))],
        "candidate_rows": int(
            health.get(
                "candidate_dataset_rows",
                coverage.get("matches_finished_admitted", 0),
            )
        ),
        "candidate_minimum_rows": int(
            health.get("candidate_minimum_rows", 1500)
        ),
        "active_model_id": str(
            health.get("active_shadow_model_id", active_model)
        ),
        "governor_status": str(
            validation.get("status", "WAITING_MINIMUM_SAMPLE")
        ),
        "governor_enabled": bool(
            health.get("automatic_shadow_promotion_allowed", False)
        ),
        "shadow_only": True,
        "real_execution_allowed": False,
    }
