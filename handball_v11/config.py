from __future__ import annotations

import os
from dataclasses import dataclass

from settings_v81 import load_settings


class HandballConfigurationError(RuntimeError):
    pass


def _float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError) as exc:
        raise HandballConfigurationError(f"{name} must be numeric") from exc
    if not minimum <= value <= maximum:
        raise HandballConfigurationError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return value


def _enabled(name: str, default: bool) -> bool:
    fallback = "1" if default else "0"
    return os.getenv(name, fallback).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@dataclass(frozen=True)
class HandballSettings:
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
    empty_odds_retry_hours: int
    lookahead_days: int
    maximum_odds_requests_per_cycle: int
    minimum_bookmakers: int
    training_min_games: int
    training_min_new_games: int
    validation_min_train_games: int
    validation_min_test_games: int
    validation_min_folds: int
    validation_max_folds: int
    autonomous_governor_enabled: bool
    live_shadow_min_samples: int
    live_shadow_report_step: int
    live_shadow_positive_reports: int
    live_shadow_rollback_reports: int
    live_shadow_drift_psi_limit: float


def load_handball_settings(*, require_key: bool = True) -> HandballSettings:
    runtime = load_settings()
    settings = HandballSettings(
        enabled=runtime.handball_enabled,
        shadow_only=runtime.handball_shadow_only,
        poll_minutes=runtime.handball_poll_minutes,
        backfill_days=runtime.handball_backfill_days,
        api_key=os.getenv("HANDBALL_API_SPORTS_KEY", "").strip(),
        api_base_url=os.getenv(
            "HANDBALL_API_SPORTS_BASE_URL",
            "https://v1.handball.api-sports.io",
        ).rstrip("/"),
        timezone=os.getenv("BETBOT_HANDBALL_TIMEZONE", "Europe/Warsaw").strip(),
        minimum_edge=_float("BETBOT_HANDBALL_MIN_EDGE", 0.03, 0.0, 0.50),
        request_timeout_seconds=_float(
            "BETBOT_HANDBALL_REQUEST_TIMEOUT_SECONDS", 20.0, 3.0, 120.0
        ),
        retry_attempts=int(
            _float("BETBOT_HANDBALL_RETRY_ATTEMPTS", 3, 1, 6)
        ),
        retry_backoff_seconds=_float(
            "BETBOT_HANDBALL_RETRY_BACKOFF_SECONDS", 1.5, 0.1, 30.0
        ),
        odds_refresh_hours=int(
            _float("BETBOT_HANDBALL_ODDS_REFRESH_HOURS", 12, 1, 24)
        ),
        empty_odds_retry_hours=int(
            _float("BETBOT_HANDBALL_EMPTY_ODDS_RETRY_HOURS", 6, 1, 24)
        ),
        lookahead_days=int(
            _float("BETBOT_HANDBALL_LOOKAHEAD_DAYS", 7, 1, 21)
        ),
        maximum_odds_requests_per_cycle=int(
            _float("BETBOT_HANDBALL_MAX_ODDS_REQUESTS_PER_CYCLE", 80, 1, 500)
        ),
        minimum_bookmakers=int(
            _float("BETBOT_HANDBALL_MIN_BOOKMAKERS", 2, 1, 20)
        ),
        training_min_games=int(
            _float("BETBOT_HANDBALL_TRAIN_MIN_GAMES", 100, 30, 100000)
        ),
        training_min_new_games=int(
            _float("BETBOT_HANDBALL_TRAIN_MIN_NEW_GAMES", 25, 1, 10000)
        ),
        validation_min_train_games=int(
            _float("BETBOT_HANDBALL_VALIDATION_MIN_TRAIN_GAMES", 40, 20, 100000)
        ),
        validation_min_test_games=int(
            _float("BETBOT_HANDBALL_VALIDATION_MIN_TEST_GAMES", 20, 10, 10000)
        ),
        validation_min_folds=int(
            _float("BETBOT_HANDBALL_VALIDATION_MIN_FOLDS", 3, 2, 10)
        ),
        validation_max_folds=int(
            _float("BETBOT_HANDBALL_VALIDATION_MAX_FOLDS", 5, 2, 20)
        ),
        autonomous_governor_enabled=_enabled(
            "BETBOT_HANDBALL_AUTONOMOUS_GOVERNOR_ENABLED",
            True,
        ),
        live_shadow_min_samples=int(
            _float("BETBOT_HANDBALL_LIVE_MIN_SAMPLES", 30, 20, 10000)
        ),
        live_shadow_report_step=int(
            _float("BETBOT_HANDBALL_LIVE_REPORT_STEP", 10, 5, 1000)
        ),
        live_shadow_positive_reports=int(
            _float("BETBOT_HANDBALL_LIVE_POSITIVE_REPORTS", 3, 2, 10)
        ),
        live_shadow_rollback_reports=int(
            _float("BETBOT_HANDBALL_LIVE_ROLLBACK_REPORTS", 3, 2, 10)
        ),
        live_shadow_drift_psi_limit=_float(
            "BETBOT_HANDBALL_DRIFT_PSI_LIMIT",
            0.25,
            0.05,
            1.0,
        ),
    )
    if settings.enabled and not settings.shadow_only:
        raise HandballConfigurationError("Handball v11 must remain shadow-only")
    if settings.enabled and require_key and not settings.api_key:
        raise HandballConfigurationError(
            "HANDBALL_API_SPORTS_KEY is required when handball is enabled"
        )
    if settings.validation_max_folds < settings.validation_min_folds:
        raise HandballConfigurationError(
            "BETBOT_HANDBALL_VALIDATION_MAX_FOLDS must be at least "
            "BETBOT_HANDBALL_VALIDATION_MIN_FOLDS"
        )
    return settings

