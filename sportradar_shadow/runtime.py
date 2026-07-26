from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from . import SCHEMA_VERSION
from .client import SportradarClient, SportradarProviderError
from .config import SportradarSettings, load_sportradar_settings
from .normalize import normalize_events, normalize_odds, schedule_event_ids
from .storage import SportradarShadowStorage


SPORTS = ("football", "volleyball", "handball")
RUNTIME_VERSION = "1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _days(settings: SportradarSettings) -> list[date]:
    today = datetime.now(timezone.utc).date()
    return [
        today + timedelta(days=offset)
        for offset in range(-settings.lookback_days, settings.lookahead_days + 1)
    ]


def run_cycle(
    storage: SportradarShadowStorage,
    client: SportradarClient,
    settings: SportradarSettings,
) -> dict[str, Any]:
    if not settings.shadow_only:
        raise RuntimeError("Sportradar runtime refuses non-shadow execution")
    cycle_started = _utc_now()
    requested_days = _days(settings)
    sport_health: dict[str, dict[str, int]] = {
        sport: {
            "summary_requests": 0,
            "summary_failures": 0,
            "events_received": 0,
            "events_inserted": 0,
            "quarantined": 0,
            "odds_schedule_requests": 0,
            "odds_schedule_failures": 0,
            "odds_market_requests": 0,
            "odds_market_failures": 0,
            "odds_received": 0,
            "odds_inserted": 0,
        }
        for sport in SPORTS
    }

    for sport in SPORTS:
        for day in requested_days:
            sport_health[sport]["summary_requests"] += 1
            try:
                response = client.daily_summaries(sport, day)
                events, rejected = normalize_events(
                    response.payload,
                    sport=sport,
                    source_endpoint=response.url,
                )
                sport_health[sport]["events_received"] += len(events)
                sport_health[sport]["events_inserted"] += storage.save_events(events)
                sport_health[sport]["quarantined"] += storage.quarantine(rejected)
            except SportradarProviderError:
                sport_health[sport]["summary_failures"] += 1

    if settings.odds_enabled:
        future_days = [
            day for day in requested_days if day >= datetime.now(timezone.utc).date()
        ]
        market_candidates: list[tuple[str, str, str]] = []
        for sport in SPORTS:
            for day in future_days:
                sport_health[sport]["odds_schedule_requests"] += 1
                try:
                    response = client.odds_daily_schedule(sport, day)
                    for event_id, scheduled_at in schedule_event_ids(response.payload):
                        market_candidates.append((scheduled_at, sport, event_id))
                except SportradarProviderError:
                    sport_health[sport]["odds_schedule_failures"] += 1
        unique_candidates = {
            (sport, event_id): scheduled_at
            for scheduled_at, sport, event_id in market_candidates
        }
        ordered = sorted(
            (
                (scheduled_at, sport, event_id)
                for (sport, event_id), scheduled_at in unique_candidates.items()
            ),
            key=lambda item: (item[0], item[1], item[2]),
        )[: settings.odds_maximum_events_per_cycle]
        for _, sport, event_id in ordered:
            sport_health[sport]["odds_market_requests"] += 1
            try:
                response = client.odds_event_markets(event_id)
                quotes, rejected = normalize_odds(
                    response.payload,
                    sport=sport,
                    event_id=event_id,
                    source_endpoint=response.url,
                )
                sport_health[sport]["odds_received"] += len(quotes)
                sport_health[sport]["odds_inserted"] += storage.save_odds(quotes)
                sport_health[sport]["quarantined"] += storage.quarantine(rejected)
            except SportradarProviderError:
                sport_health[sport]["odds_market_failures"] += 1

    request_failures = sum(
        item["summary_failures"]
        + item["odds_schedule_failures"]
        + item["odds_market_failures"]
        for item in sport_health.values()
    )
    request_total = sum(
        item["summary_requests"]
        + item["odds_schedule_requests"]
        + item["odds_market_requests"]
        for item in sport_health.values()
    )
    status = (
        "HEALTHY"
        if request_failures == 0
        else "DEGRADED"
        if request_failures < request_total
        else "FAILED"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "status": status,
        "cycle_started_at": cycle_started,
        "updated_at": _utc_now(),
        "settings": settings.public_snapshot(),
        "sports": sport_health,
        "provider_requests": request_total,
        "provider_failures": request_failures,
        "storage_counts": storage.counts(),
        "shadow_only": True,
        "active_model_modified": False,
        "source_history_modified": False,
        "real_execution_allowed": False,
        "automatic_training_admission": False,
        "automatic_model_promotion_allowed": False,
    }


def main() -> int:
    settings = load_sportradar_settings()
    if not settings.enabled:
        print("SPORTRADAR SHADOW DISABLED", flush=True)
        return 0
    storage = SportradarShadowStorage()
    storage.initialize()
    client = SportradarClient(settings, observer=storage.record_provider_call)
    print(
        json.dumps(
            {
                "event": "SPORTRADAR_SHADOW_START",
                "runtime_version": RUNTIME_VERSION,
                "poll_minutes": settings.poll_minutes,
                "access_level": settings.access_level,
                "shadow_only": True,
                "api_key_configured": bool(settings.api_key),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    while True:
        try:
            health = run_cycle(storage, client, settings)
        except Exception as exc:
            health = {
                "schema_version": SCHEMA_VERSION,
                "runtime_version": RUNTIME_VERSION,
                "status": "FAILED",
                "error_type": type(exc).__name__,
                "error": str(exc)[:500],
                "updated_at": _utc_now(),
                "contains_secrets": False,
                "shadow_only": True,
                "active_model_modified": False,
                "source_history_modified": False,
                "real_execution_allowed": False,
                "automatic_training_admission": False,
                "automatic_model_promotion_allowed": False,
            }
        storage.write_health(health)
        print(
            json.dumps(
                {"event": "SPORTRADAR_SHADOW_CYCLE", **health},
                sort_keys=True,
            ),
            flush=True,
        )
        time.sleep(settings.poll_minutes * 60)


if __name__ == "__main__":
    raise SystemExit(main())

