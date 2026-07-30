from __future__ import annotations

import json
import time
from collections import Counter
from datetime import date, timedelta
from typing import Any

from . import RUNTIME_VERSION, SCHEMA_VERSION
from .client import (
    ApiSportsBasketballClient,
    BasketballProviderError,
    BasketballRequestBudgetExhausted,
)
from .config import BasketballSettings, load_basketball_settings
from .domain import UPCOMING_STATUSES, BasketballGame, utc_now
from .storage import BasketballStorage


_CIRCUIT_CATEGORIES = {
    "AUTH",
    "AUTH_OR_ENTITLEMENT",
    "ENTITLEMENT",
    "QUOTA",
    "RATE_LIMIT",
    "ENDPOINT_UNAVAILABLE",
    "PROVIDER_4XX",
    "PROVIDER_RESPONSE",
}


def _json_list(raw: str) -> list[str]:
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(value, list):
        return []
    return [
        str(item)
        for item in value
        if isinstance(item, str) and len(item) == 10
    ]


def _backfill_cursor(storage: BasketballStorage) -> int:
    try:
        return max(0, int(storage.state("backfill_cursor_days") or "0"))
    except ValueError:
        return 0


def _date_plan(
    storage: BasketballStorage, settings: BasketballSettings
) -> dict[str, list[tuple[str, int | None]]]:
    today = date.today()
    live = [
        ((today + timedelta(days=offset)).isoformat(), None)
        for offset in range(settings.lookahead_days + 1)
    ]
    failed = _json_list(storage.state("backfill_failed_dates"))
    retry = [(value, None) for value in failed[
        :settings.backfill_retry_dates_per_cycle
    ]]
    cursor = min(_backfill_cursor(storage), settings.backfill_days)
    upper = min(
        settings.backfill_days,
        cursor + settings.backfill_days_per_cycle,
    )
    new_backfill = [
        ((today - timedelta(days=offset)).isoformat(), offset)
        for offset in range(cursor + 1, upper + 1)
    ]
    return {
        "live": live,
        "retry": retry,
        "new_backfill": new_backfill,
    }


def run_cycle(
    storage: BasketballStorage,
    client: ApiSportsBasketballClient,
    settings: BasketballSettings,
) -> dict[str, Any]:
    plan = _date_plan(storage, settings)
    planned = plan["live"] + plan["retry"] + plan["new_backfill"]
    live_dates = {item[0] for item in plan["live"]}
    games: list[BasketballGame] = []
    days_succeeded = 0
    days_failed = 0
    days_attempted = 0
    failed_categories: Counter[str] = Counter()
    failed_backfill = _json_list(storage.state("backfill_failed_dates"))
    attempted_new_offsets: list[int] = []
    circuit_open = False
    request_budget_reached = False
    retry_after_seconds: int | None = None
    quota_limit: int | None = None
    quota_remaining: int | None = None

    begin_cycle = getattr(client, "begin_cycle", None)
    if callable(begin_cycle):
        begin_cycle(settings.maximum_requests_per_cycle)

    for value, backfill_offset in planned:
        if circuit_open or request_budget_reached:
            break
        days_attempted += 1
        if backfill_offset is not None:
            attempted_new_offsets.append(backfill_offset)
        try:
            games.extend(client.games_for_date(value))
            days_succeeded += 1
            if value in failed_backfill:
                failed_backfill.remove(value)
        except BasketballRequestBudgetExhausted:
            request_budget_reached = True
            failed_categories["REQUEST_BUDGET"] += 1
            if value not in live_dates and value not in failed_backfill:
                failed_backfill.append(value)
        except BasketballProviderError as exc:
            days_failed += 1
            category = str(getattr(exc, "category", "") or "PROVIDER")
            failed_categories[category] += 1
            if value not in live_dates:
                if value not in failed_backfill:
                    failed_backfill.append(value)
            if category in _CIRCUIT_CATEGORIES:
                circuit_open = True
                retry_after_seconds = getattr(
                    exc, "retry_after_seconds", None
                )
                quota_limit = getattr(exc, "quota_limit", None)
                quota_remaining = getattr(exc, "quota_remaining", None)

    if attempted_new_offsets:
        storage.set_state(
            "backfill_cursor_days", str(max(attempted_new_offsets))
        )
    failed_backfill = list(dict.fromkeys(failed_backfill))[
        :settings.backfill_days
    ]
    storage.set_state(
        "backfill_failed_dates", json.dumps(failed_backfill, sort_keys=True)
    )
    cursor = min(_backfill_cursor(storage), settings.backfill_days)
    backfill_complete = (
        cursor >= settings.backfill_days and not failed_backfill
    )
    storage.set_state(
        "initial_backfill_complete", "1" if backfill_complete else "0"
    )
    saved = storage.upsert_games(games)

    odds_attempted = 0
    odds_failed = 0
    odds_empty = 0
    odds_quotes = 0
    for game in sorted(games, key=lambda item: item.scheduled_at):
        if (
            circuit_open
            or request_budget_reached
            or game.status.upper() not in UPCOMING_STATUSES
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
        except BasketballRequestBudgetExhausted:
            request_budget_reached = True
            failed_categories["REQUEST_BUDGET"] += 1
            break
        except BasketballProviderError as exc:
            odds_failed += 1
            category = str(getattr(exc, "category", "") or "PROVIDER")
            failed_categories[category] += 1
            if category in _CIRCUIT_CATEGORIES:
                circuit_open = True
                retry_after_seconds = getattr(
                    exc, "retry_after_seconds", None
                )
                quota_limit = getattr(exc, "quota_limit", None)
                quota_remaining = getattr(exc, "quota_remaining", None)
                break
            continue
        if not quotes:
            odds_empty += 1
        odds_quotes += storage.save_odds(quotes)

    if circuit_open:
        storage.set_state(
            "provider_circuit",
            json.dumps(
                {
                    "open": True,
                    "failure_categories": dict(failed_categories),
                    "retry_after_seconds": retry_after_seconds,
                    "quota_limit": quota_limit,
                    "quota_remaining": quota_remaining,
                    "updated_at": utc_now(),
                },
                sort_keys=True,
            ),
        )
    else:
        storage.set_state(
            "provider_circuit",
            json.dumps({"open": False, "updated_at": utc_now()}),
        )

    settlement = storage.settle_finished_games()
    coverage = storage.coverage_summary()
    if circuit_open:
        status = "PROVIDER_CIRCUIT_OPEN"
    elif request_budget_reached:
        status = "REQUEST_BUDGET_REACHED"
    elif days_failed:
        status = "LIMITED_BY_PROVIDER"
    else:
        status = "HEALTHY"
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
        "days_requested": len(planned),
        "days_attempted": days_attempted,
        "days_skipped_after_circuit": len(planned) - days_attempted,
        "days_succeeded": days_succeeded,
        "days_failed": days_failed,
        "provider_circuit_open": circuit_open,
        "provider_failure_categories": dict(failed_categories),
        "provider_retry_after_seconds": retry_after_seconds,
        "provider_quota_limit": quota_limit,
        "provider_quota_remaining": quota_remaining,
        "request_budget_per_cycle": settings.maximum_requests_per_cycle,
        "requests_made": int(getattr(client, "requests_made", 0)),
        "request_budget_reached": request_budget_reached,
        "backfill_cursor_days": cursor,
        "backfill_target_days": settings.backfill_days,
        "backfill_failed_dates": len(failed_backfill),
        "backfill_complete": backfill_complete,
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
