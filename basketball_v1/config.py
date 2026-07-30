from __future__ import annotations

import os
from dataclasses import dataclass

from settings_v81 import load_settings


class BasketballConfigurationError(RuntimeError):
    pass


def _integer(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError) as exc:
        raise BasketballConfigurationError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise BasketballConfigurationError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return value


def _number(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError) as exc:
        raise BasketballConfigurationError(f"{name} must be numeric") from exc
    if not minimum <= value <= maximum:
        raise BasketballConfigurationError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return value


@dataclass(frozen=True)
class BasketballSettings:
    enabled: bool
    shadow_only: bool
    poll_minutes: int
    backfill_days: int
    lookahead_days: int
    api_key: str
    api_base_url: str
    timezone: str
    request_timeout_seconds: float
    retry_attempts: int
    retry_backoff_seconds: float
    odds_refresh_hours: int
    empty_odds_retry_hours: int
    maximum_odds_requests_per_cycle: int


def load_basketball_settings(
    *, require_key: bool = True
) -> BasketballSettings:
    runtime = load_settings()
    settings = BasketballSettings(
        enabled=runtime.basketball_enabled,
        shadow_only=runtime.basketball_shadow_only,
        poll_minutes=runtime.basketball_poll_minutes,
        backfill_days=runtime.basketball_backfill_days,
        lookahead_days=_integer(
            "BETBOT_BASKETBALL_LOOKAHEAD_DAYS", 7, 1, 21
        ),
        api_key=(
            os.getenv("BASKETBALL_API_SPORTS_KEY", "").strip()
            or os.getenv("API_SPORTS_KEY", "").strip()
        ),
        api_base_url=os.getenv(
            "BASKETBALL_API_SPORTS_BASE_URL",
            "https://v1.basketball.api-sports.io",
        ).rstrip("/"),
        timezone=os.getenv(
            "BETBOT_BASKETBALL_TIMEZONE", "Europe/Warsaw"
        ).strip(),
        request_timeout_seconds=_number(
            "BETBOT_BASKETBALL_REQUEST_TIMEOUT_SECONDS", 20.0, 3.0, 120.0
        ),
        retry_attempts=_integer(
            "BETBOT_BASKETBALL_RETRY_ATTEMPTS", 2, 1, 5
        ),
        retry_backoff_seconds=_number(
            "BETBOT_BASKETBALL_RETRY_BACKOFF_SECONDS", 1.5, 0.1, 30.0
        ),
        odds_refresh_hours=_integer(
            "BETBOT_BASKETBALL_ODDS_REFRESH_HOURS", 6, 1, 24
        ),
        empty_odds_retry_hours=_integer(
            "BETBOT_BASKETBALL_EMPTY_ODDS_RETRY_HOURS", 3, 1, 24
        ),
        maximum_odds_requests_per_cycle=_integer(
            "BETBOT_BASKETBALL_MAX_ODDS_REQUESTS_PER_CYCLE", 80, 1, 500
        ),
    )
    if settings.enabled and not settings.shadow_only:
        raise BasketballConfigurationError(
            "Basketball v1 must remain shadow-only"
        )
    if settings.enabled and require_key and not settings.api_key:
        raise BasketballConfigurationError(
            "BASKETBALL_API_SPORTS_KEY or API_SPORTS_KEY is required"
        )
    return settings

