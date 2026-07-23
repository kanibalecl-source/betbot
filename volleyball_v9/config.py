from __future__ import annotations

import os
from dataclasses import dataclass

from settings_v81 import load_settings


class VolleyballConfigurationError(RuntimeError):
    pass


def _float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError) as exc:
        raise VolleyballConfigurationError(f"{name} must be numeric") from exc
    if not minimum <= value <= maximum:
        raise VolleyballConfigurationError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return value


@dataclass(frozen=True)
class VolleyballSettings:
    enabled: bool
    shadow_only: bool
    poll_minutes: int
    backfill_days: int
    api_key: str
    api_base_url: str
    timezone: str
    minimum_edge: float
    request_timeout_seconds: float
    retry_attempts: int
    retry_backoff_seconds: float
    odds_refresh_hours: int
    minimum_bookmakers: int
    training_min_games: int
    training_min_new_games: int
    validation_min_train_games: int
    validation_min_test_games: int
    validation_min_folds: int
    validation_max_folds: int


def load_volleyball_settings(*, require_key: bool = True) -> VolleyballSettings:
    runtime = load_settings()
    settings = VolleyballSettings(
        enabled=runtime.volleyball_enabled,
        shadow_only=runtime.volleyball_shadow_only,
        poll_minutes=runtime.volleyball_poll_minutes,
        backfill_days=runtime.volleyball_backfill_days,
        api_key=os.getenv("VOLLEYBALL_API_SPORTS_KEY", "").strip(),
        api_base_url=os.getenv(
            "VOLLEYBALL_API_SPORTS_BASE_URL",
            "https://v1.volleyball.api-sports.io",
        ).rstrip("/"),
        timezone=os.getenv("BETBOT_VOLLEYBALL_TIMEZONE", "Europe/Warsaw").strip(),
        minimum_edge=_float("BETBOT_VOLLEYBALL_MIN_EDGE", 0.03, 0.0, 0.50),
        request_timeout_seconds=_float(
            "BETBOT_VOLLEYBALL_REQUEST_TIMEOUT_SECONDS", 20.0, 3.0, 120.0
        ),
        retry_attempts=int(
            _float("BETBOT_VOLLEYBALL_RETRY_ATTEMPTS", 3, 1, 6)
        ),
        retry_backoff_seconds=_float(
            "BETBOT_VOLLEYBALL_RETRY_BACKOFF_SECONDS", 1.5, 0.1, 30.0
        ),
        odds_refresh_hours=int(
            _float("BETBOT_VOLLEYBALL_ODDS_REFRESH_HOURS", 12, 1, 24)
        ),
        minimum_bookmakers=int(
            _float("BETBOT_VOLLEYBALL_MIN_BOOKMAKERS", 2, 1, 20)
        ),
        training_min_games=int(
            _float("BETBOT_VOLLEYBALL_TRAIN_MIN_GAMES", 100, 30, 100000)
        ),
        training_min_new_games=int(
            _float("BETBOT_VOLLEYBALL_TRAIN_MIN_NEW_GAMES", 25, 1, 10000)
        ),
        validation_min_train_games=int(
            _float("BETBOT_VOLLEYBALL_VALIDATION_MIN_TRAIN_GAMES", 40, 20, 100000)
        ),
        validation_min_test_games=int(
            _float("BETBOT_VOLLEYBALL_VALIDATION_MIN_TEST_GAMES", 20, 10, 10000)
        ),
        validation_min_folds=int(
            _float("BETBOT_VOLLEYBALL_VALIDATION_MIN_FOLDS", 3, 2, 10)
        ),
        validation_max_folds=int(
            _float("BETBOT_VOLLEYBALL_VALIDATION_MAX_FOLDS", 5, 2, 20)
        ),
    )
    if settings.enabled and not settings.shadow_only:
        raise VolleyballConfigurationError("Volleyball v9.0 must remain shadow-only")
    if settings.enabled and require_key and not settings.api_key:
        raise VolleyballConfigurationError(
            "VOLLEYBALL_API_SPORTS_KEY is required when volleyball is enabled"
        )
    if settings.validation_max_folds < settings.validation_min_folds:
        raise VolleyballConfigurationError(
            "BETBOT_VOLLEYBALL_VALIDATION_MAX_FOLDS must be at least "
            "BETBOT_VOLLEYBALL_VALIDATION_MIN_FOLDS"
        )
    return settings
