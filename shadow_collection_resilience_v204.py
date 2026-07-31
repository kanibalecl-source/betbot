"""Incremental and quota-aware date collection for isolated shadow sports."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Iterable


IMMEDIATE_CIRCUIT_CATEGORIES = {
    "AUTH",
    "QUOTA",
    "RATE_LIMIT",
    "ENDPOINT_UNAVAILABLE",
    "PROVIDER_4XX",
    "PROVIDER_RESPONSE",
}


def _json_dates(raw: str | None) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(value, list):
        return []
    dates: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        try:
            parsed = date.fromisoformat(item)
        except ValueError:
            continue
        dates.append(parsed.isoformat())
    return list(dict.fromkeys(dates))


def _cursor(storage: Any, backfill_days: int) -> int:
    raw = storage.state("backfill_cursor_days")
    if raw in (None, "") and storage.state("initial_backfill_complete") == "1":
        return max(0, int(backfill_days))
    try:
        return max(0, min(int(raw or "0"), int(backfill_days)))
    except (TypeError, ValueError):
        return 0


@dataclass
class CollectionResult:
    games: list[Any] = field(default_factory=list)
    days_requested: int = 0
    days_attempted: int = 0
    days_succeeded: int = 0
    days_failed: int = 0
    days_skipped_after_circuit: int = 0
    provider_circuit_open: bool = False
    request_budget_reached: bool = False
    provider_failure_categories: Counter[str] = field(default_factory=Counter)
    provider_retry_after_seconds: int | None = None
    provider_quota_limit: int | None = None
    provider_quota_remaining: int | None = None
    date_scope_limited_days: int = 0
    backfill_cursor_days: int = 0
    backfill_target_days: int = 0
    backfill_failed_dates: int = 0
    backfill_complete: bool = False
    requests_made: int = 0

    def note_provider_error(self, exc: Exception) -> str:
        category = str(getattr(exc, "category", "") or "PROVIDER")
        self.provider_failure_categories[category] += 1
        if category in IMMEDIATE_CIRCUIT_CATEGORIES:
            self.provider_circuit_open = True
            self.provider_retry_after_seconds = getattr(
                exc, "retry_after_seconds", None
            )
            self.provider_quota_limit = getattr(exc, "quota_limit", None)
            self.provider_quota_remaining = getattr(
                exc, "quota_remaining", None
            )
        return category

    def status(self, *, odds_failed: int = 0) -> str:
        if self.provider_circuit_open:
            return "PROVIDER_CIRCUIT_OPEN"
        if self.request_budget_reached:
            return "REQUEST_BUDGET_REACHED"
        if self.days_failed or odds_failed:
            return "LIMITED_BY_PROVIDER"
        return "HEALTHY"


def collect_games_incrementally(
    *,
    storage: Any,
    client: Any,
    settings: Any,
    provider_error_type: type[Exception],
    request_budget_error_type: type[Exception],
    open_pick_dates: Iterable[str] = (),
) -> CollectionResult:
    """Collect live and historical dates without restarting full backfill."""
    today = date.today()
    planned: dict[str, dict[str, Any]] = {}

    def add(
        value: date, *, live: bool, retry: bool = False,
        backfill_offset: int | None = None,
    ) -> None:
        key = value.isoformat()
        current = planned.get(key)
        if current is None:
            planned[key] = {
                "value": value,
                "live": live,
                "retry": retry,
                "backfill_offset": backfill_offset,
            }
            return
        current["live"] = bool(current["live"] or live)
        current["retry"] = bool(current["retry"] or retry)
        if backfill_offset is not None:
            current["backfill_offset"] = backfill_offset

    for offset in range(int(settings.lookahead_days) + 1):
        add(today + timedelta(days=offset), live=True)
    for raw in open_pick_dates:
        try:
            add(date.fromisoformat(str(raw)), live=True)
        except ValueError:
            continue

    failed_dates = _json_dates(storage.state("backfill_failed_dates"))
    retry_limit = int(settings.backfill_retry_dates_per_cycle)
    for raw in failed_dates[:retry_limit]:
        add(date.fromisoformat(raw), live=False, retry=True)

    cursor = _cursor(storage, int(settings.backfill_days))
    upper = min(
        int(settings.backfill_days),
        cursor + int(settings.backfill_days_per_cycle),
    )
    for offset in range(cursor + 1, upper + 1):
        add(
            today - timedelta(days=offset),
            live=False,
            backfill_offset=offset,
        )

    result = CollectionResult(
        days_requested=len(planned),
        backfill_cursor_days=cursor,
        backfill_target_days=int(settings.backfill_days),
    )
    begin_cycle = getattr(client, "begin_cycle", None)
    if callable(begin_cycle):
        begin_cycle(int(settings.maximum_requests_per_cycle))

    games: dict[str, Any] = {}
    attempted_offsets: list[int] = []
    entitlement_without_success = 0

    for item in planned.values():
        if result.provider_circuit_open or result.request_budget_reached:
            break
        result.days_attempted += 1
        backfill_offset = item["backfill_offset"]
        if backfill_offset is not None:
            attempted_offsets.append(int(backfill_offset))
        day_key = item["value"].isoformat()
        try:
            for game in client.games_for_date(item["value"]):
                game_id = str(getattr(game, "game_id", "") or "")
                if game_id:
                    games[game_id] = game
            result.days_succeeded += 1
            entitlement_without_success = 0
            if day_key in failed_dates:
                failed_dates.remove(day_key)
        except request_budget_error_type:
            result.request_budget_reached = True
            result.provider_failure_categories["REQUEST_BUDGET"] += 1
            if not item["live"] and day_key not in failed_dates:
                failed_dates.append(day_key)
        except provider_error_type as exc:
            result.days_failed += 1
            category = result.note_provider_error(exc)
            if not item["live"] and day_key not in failed_dates:
                failed_dates.append(day_key)
            if category in {"ENTITLEMENT", "COVERAGE"}:
                result.date_scope_limited_days += 1
            if category == "ENTITLEMENT":
                if result.days_succeeded == 0:
                    entitlement_without_success += 1
                if (
                    result.days_succeeded == 0
                    and entitlement_without_success
                    >= int(settings.entitlement_circuit_threshold)
                ):
                    result.provider_circuit_open = True
                    result.provider_retry_after_seconds = getattr(
                        exc, "retry_after_seconds", None
                    )
                    result.provider_quota_limit = getattr(
                        exc, "quota_limit", None
                    )
                    result.provider_quota_remaining = getattr(
                        exc, "quota_remaining", None
                    )

    if attempted_offsets:
        cursor = max(cursor, max(attempted_offsets))
        storage.set_state("backfill_cursor_days", str(cursor))
    failed_dates = list(dict.fromkeys(failed_dates))[
        :int(settings.backfill_days)
    ]
    storage.set_state(
        "backfill_failed_dates", json.dumps(failed_dates, sort_keys=True)
    )
    result.backfill_cursor_days = cursor
    result.backfill_failed_dates = len(failed_dates)
    result.backfill_complete = (
        cursor >= int(settings.backfill_days) and not failed_dates
    )
    storage.set_state(
        "initial_backfill_complete",
        "1" if result.backfill_complete else "0",
    )
    result.days_skipped_after_circuit = (
        result.days_requested - result.days_attempted
    )
    result.games = list(games.values())
    result.requests_made = int(getattr(client, "requests_made", 0))
    return result
