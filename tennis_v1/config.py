from __future__ import annotations

import os
from dataclasses import dataclass

from settings_v81 import load_settings


class TennisConfigurationError(RuntimeError):
    pass


def _number(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError) as exc:
        raise TennisConfigurationError(f"{name} must be numeric") from exc
    if not minimum <= value <= maximum:
        raise TennisConfigurationError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return value


def _enabled(name: str, default: bool) -> bool:
    return os.getenv(name, "1" if default else "0").strip().lower() in {
        "1", "true", "yes", "on",
    }


@dataclass(frozen=True)
class TennisSettings:
    enabled: bool
    shadow_only: bool
    poll_minutes: int
    backfill_days: int
    lookahead_days: int
    sportradar_api_key: str
    sportradar_access_level: str
    sportradar_base_url: str
    odds_api_key: str
    odds_api_base_url: str
    odds_regions: str
    odds_scores_days: int
    request_timeout_seconds: float
    retry_attempts: int
    sportradar_max_schedule_days: int
    minimum_bookmakers: int
    minimum_edge: float
    maximum_odds_sports_per_cycle: int
    training_min_matches: int
    training_min_surface_matches: int
    training_min_new_matches: int
    validation_test_matches: int
    validation_min_folds: int
    validation_min_brier_improvement: float
    autonomous_governor_enabled: bool
    include_atp: bool
    include_wta: bool
    include_challenger: bool
    include_itf: bool
    include_doubles: bool


def load_tennis_settings(*, require_keys: bool = True) -> TennisSettings:
    runtime = load_settings()
    settings = TennisSettings(
        enabled=runtime.tennis_enabled,
        shadow_only=runtime.tennis_shadow_only,
        poll_minutes=runtime.tennis_poll_minutes,
        backfill_days=runtime.tennis_backfill_days,
        lookahead_days=int(_number("BETBOT_TENNIS_LOOKAHEAD_DAYS", 3, 1, 14)),
        sportradar_api_key=os.getenv("SPORTRADAR_API_KEY", "").strip(),
        sportradar_access_level=os.getenv(
            "BETBOT_TENNIS_SPORTRADAR_ACCESS_LEVEL", "trial"
        ).strip().lower(),
        sportradar_base_url=os.getenv(
            "BETBOT_TENNIS_SPORTRADAR_BASE_URL",
            "https://api.sportradar.com/tennis",
        ).rstrip("/"),
        odds_api_key=(
            os.getenv("THE_ODDS_API_KEY", "").strip()
            or os.getenv("ODDS_API_KEY", "").strip()
        ),
        odds_api_base_url=os.getenv(
            "BETBOT_TENNIS_ODDS_API_BASE_URL",
            "https://api.the-odds-api.com/v4",
        ).rstrip("/"),
        odds_regions=os.getenv(
            "BETBOT_TENNIS_ODDS_REGIONS", "eu,uk"
        ).strip(),
        odds_scores_days=int(
            _number("BETBOT_TENNIS_ODDS_SCORES_DAYS", 3, 1, 3)
        ),
        request_timeout_seconds=_number(
            "BETBOT_TENNIS_REQUEST_TIMEOUT_SECONDS", 20, 3, 120
        ),
        retry_attempts=int(_number("BETBOT_TENNIS_RETRY_ATTEMPTS", 2, 1, 5)),
        sportradar_max_schedule_days=int(
            _number("BETBOT_TENNIS_SPORTRADAR_MAX_SCHEDULE_DAYS", 7, 1, 31)
        ),
        minimum_bookmakers=int(
            _number("BETBOT_TENNIS_MIN_BOOKMAKERS", 2, 2, 20)
        ),
        minimum_edge=_number("BETBOT_TENNIS_MIN_EDGE", 0.03, 0.0, 0.30),
        maximum_odds_sports_per_cycle=int(
            _number("BETBOT_TENNIS_MAX_ODDS_SPORTS_PER_CYCLE", 12, 1, 80)
        ),
        training_min_matches=int(
            _number("BETBOT_TENNIS_TRAIN_MIN_MATCHES", 1500, 500, 1000000)
        ),
        training_min_surface_matches=int(
            _number("BETBOT_TENNIS_TRAIN_MIN_SURFACE_MATCHES", 300, 100, 100000)
        ),
        training_min_new_matches=int(
            _number("BETBOT_TENNIS_TRAIN_MIN_NEW_MATCHES", 100, 25, 10000)
        ),
        validation_test_matches=int(
            _number("BETBOT_TENNIS_VALIDATION_TEST_MATCHES", 200, 50, 5000)
        ),
        validation_min_folds=int(
            _number("BETBOT_TENNIS_VALIDATION_MIN_FOLDS", 4, 3, 10)
        ),
        validation_min_brier_improvement=_number(
            "BETBOT_TENNIS_MIN_BRIER_IMPROVEMENT", 0.002, 0.0001, 0.05
        ),
        autonomous_governor_enabled=_enabled(
            "BETBOT_TENNIS_AUTONOMOUS_GOVERNOR_ENABLED", True
        ),
        include_atp=_enabled("BETBOT_TENNIS_INCLUDE_ATP", True),
        include_wta=_enabled("BETBOT_TENNIS_INCLUDE_WTA", True),
        include_challenger=_enabled("BETBOT_TENNIS_INCLUDE_CHALLENGER", False),
        include_itf=_enabled("BETBOT_TENNIS_INCLUDE_ITF", False),
        include_doubles=_enabled("BETBOT_TENNIS_INCLUDE_DOUBLES", False),
    )
    if settings.enabled and not settings.shadow_only:
        raise TennisConfigurationError("Tennis v1 must remain shadow-only")
    if settings.sportradar_access_level not in {"trial", "production"}:
        raise TennisConfigurationError(
            "BETBOT_TENNIS_SPORTRADAR_ACCESS_LEVEL must be trial or production"
        )
    if settings.enabled and require_keys:
        missing = []
        if not settings.sportradar_api_key:
            missing.append("SPORTRADAR_API_KEY")
        if not settings.odds_api_key:
            missing.append("THE_ODDS_API_KEY")
        if missing:
            raise TennisConfigurationError(
                "Missing tennis provider keys: " + ", ".join(missing)
            )
    if not settings.include_atp and not settings.include_wta:
        raise TennisConfigurationError("At least ATP or WTA must be enabled")
    return settings
