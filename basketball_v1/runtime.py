from __future__ import annotations

import json
import time
from datetime import date, timedelta
from typing import Any

from . import RUNTIME_VERSION, SCHEMA_VERSION
from .client import (
    ApiSportsBasketballClient,
    BasketballProviderError,
)
from .config import BasketballSettings, load_basketball_settings
from .domain import UPCOMING_STATUSES, BasketballGame, utc_now
from .storage import BasketballStorage


def _requested_dates(
    storage: BasketballStorage, settings: BasketballSettings
) -> list[str]:
    today = date.today()
    dates = [
        (today + timedelta(days=offset)).isoformat()
        for offset in range(0, settings.lookahead_days + 1)
    ]
    if settings.backfill_days and storage.state("initial_backfill_complete") != "1":
        dates.extend(
            (today - timedelta(days=offset)).isoformat()
            for offset in range(1, settings.backfill_days + 1)
        )
    return list(dict.fromkeys(dates))


def run_cycle(
    storage: BasketballStorage,
    client: ApiSportsBasketballClient,
    settings: BasketballSettings,
) -> dict[str, Any]:
    dates = _requested_dates(storage, settings)
    games: list[BasketballGame] = []
    days_succeeded = 0
    days_failed = 0
    for value in dates:
        try:
            games.extend(client.games_for_date(value))
            days_succeeded += 1
        except BasketballProviderError:
            days_failed += 1
    if not games and days_failed == len(dates):
        raise BasketballProviderError("all basketball date requests failed")

    saved = storage.upsert_games(games)
    if settings.backfill_days and days_failed == 0:
        storage.set_state("initial_backfill_complete", "1")

    odds_attempted = 0
    odds_failed = 0
    odds_empty = 0
    odds_quotes = 0
    for game in sorted(games, key=lambda item: item.scheduled_at):
        if (
            game.status.upper() not in UPCOMING_STATUSES
            or odds_attempted >= settings.maximum_odds_requests_per_cycle
        ):
            continue
        if not storage.odds_refresh_due(
            game.game_id,
            settings.odds_refresh_hours,
            empty_refresh_hours=settings.empty_odds_retry_hours,
        ):
            continue
        odds_attempted += 1
        storage.mark_odds_attempt(game.game_id)
        try:
            quotes = client.odds_for_game(game.game_id)
        except BasketballProviderError:
            odds_failed += 1
            continue
        if not quotes:
            odds_empty += 1
        odds_quotes += storage.save_odds(quotes)

    settlement = storage.settle_finished_games()
    coverage = storage.coverage_summary()
    status = "HEALTHY" if days_failed == 0 else "LIMITED_BY_PROVIDER"
    return {
        "schema_version": SCHEMA_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "status": status,
        "shadow_only": True,
        "collection_autonomous": True,
        "settlement_autonomous": True,
        "games_received": len(games),
        "games_admitted": saved["admitted"],
        "games_quarantined": saved["quarantined"],
        "days_requested": len(dates),
        "days_succeeded": days_succeeded,
        "days_failed": days_failed,
        "odds_attempted": odds_attempted,
        "odds_failed": odds_failed,
        "odds_empty_responses": odds_empty,
        "odds_quotes_saved": odds_quotes,
        "settled_this_cycle": settlement["settled"],
        "void_this_cycle": settlement["void"],
        "review_this_cycle": settlement["review"],
        "coverage": coverage,
        "database_integrity": storage.database_integrity(),
        "training_admission_allowed": False,
        "model_candidate_creation_allowed": False,
        "automatic_model_promotion_allowed": False,
        "real_execution_allowed": False,
        "active_model_modified": False,
        "football_data_modified": False,
        "volleyball_data_modified": False,
        "handball_data_modified": False,
        "tennis_data_modified": False,
        "updated_at": utc_now(),
    }


def main() -> int:
    settings = load_basketball_settings()
    if not settings.enabled:
        print("BASKETBALL v1 DISABLED", flush=True)
        return 0
    storage = BasketballStorage()
    storage.initialize()
    client = ApiSportsBasketballClient(
        settings, observer=storage.record_provider_call
    )
    print(
        f"BASKETBALL v{RUNTIME_VERSION} SHADOW START "
        f"poll={settings.poll_minutes}m "
        f"backfill={settings.backfill_days}d "
        f"lookahead={settings.lookahead_days}d",
        flush=True,
    )
    while True:
        try:
            health = run_cycle(storage, client, settings)
            storage.set_state(
                "last_health", json.dumps(health, sort_keys=True)
            )
            print(
                json.dumps(
                    {"event": "BASKETBALL_SHADOW_CYCLE", **health},
                    sort_keys=True,
                ),
                flush=True,
            )
        except Exception as exc:
            failure = {
                "event": "BASKETBALL_SHADOW_FAILED",
                "schema_version": SCHEMA_VERSION,
                "runtime_version": RUNTIME_VERSION,
                "status": "FAILED",
                "error_type": type(exc).__name__,
                "shadow_only": True,
                "training_admission_allowed": False,
                "real_execution_allowed": False,
                "active_model_modified": False,
                "football_data_modified": False,
                "volleyball_data_modified": False,
                "handball_data_modified": False,
                "tennis_data_modified": False,
                "updated_at": utc_now(),
            }
            storage.set_state(
                "last_health", json.dumps(failure, sort_keys=True)
            )
            print(json.dumps(failure, sort_keys=True), flush=True)
        time.sleep(settings.poll_minutes * 60)


if __name__ == "__main__":
    raise SystemExit(main())

