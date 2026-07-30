from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


class SportradarConfigurationError(RuntimeError):
    pass


def _bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = str(env.get(name, "1" if default else "0")).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise SportradarConfigurationError(f"{name} must be a boolean")


def _int(
    env: Mapping[str, str], name: str, default: int, minimum: int, maximum: int
) -> int:
    try:
        value = int(str(env.get(name, default)).strip())
    except (TypeError, ValueError) as exc:
        raise SportradarConfigurationError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise SportradarConfigurationError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return value


def _float(
    env: Mapping[str, str], name: str, default: float, minimum: float, maximum: float
) -> float:
    try:
        value = float(str(env.get(name, default)).strip())
    except (TypeError, ValueError) as exc:
        raise SportradarConfigurationError(f"{name} must be numeric") from exc
    if not minimum <= value <= maximum:
        raise SportradarConfigurationError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return value


@dataclass(frozen=True)
class SportradarSettings:
    enabled: bool
    shadow_only: bool
    api_key: str
    access_level: str
    language: str
    poll_minutes: int
    lookback_days: int
    lookahead_days: int
    request_timeout_seconds: int
    request_interval_seconds: float
    maximum_retries: int
    odds_enabled: bool
    odds_maximum_events_per_cycle: int
    odds_api_variant: str

    def public_snapshot(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "shadow_only": self.shadow_only,
            "access_level": self.access_level,
            "language": self.language,
            "poll_minutes": self.poll_minutes,
            "lookback_days": self.lookback_days,
            "lookahead_days": self.lookahead_days,
            "request_timeout_seconds": self.request_timeout_seconds,
            "request_interval_seconds": self.request_interval_seconds,
            "maximum_retries": self.maximum_retries,
            "odds_enabled": self.odds_enabled,
            "odds_maximum_events_per_cycle": self.odds_maximum_events_per_cycle,
            "odds_api_variant": self.odds_api_variant,
            "api_key_configured": bool(self.api_key),
        }


def load_sportradar_settings(
    env: Mapping[str, str] | None = None,
) -> SportradarSettings:
    source = os.environ if env is None else env
    access_level = str(
        source.get("BETBOT_SPORTRADAR_ACCESS_LEVEL", "trial")
    ).strip().lower()
    if access_level not in {"trial", "production"}:
        raise SportradarConfigurationError(
            "BETBOT_SPORTRADAR_ACCESS_LEVEL must be trial or production"
        )
    language = str(source.get("BETBOT_SPORTRADAR_LANGUAGE", "en")).strip().lower()
    if len(language) != 2 or not language.isalpha():
        raise SportradarConfigurationError(
            "BETBOT_SPORTRADAR_LANGUAGE must be a two-letter code"
        )
    odds_api_variant = str(
        source.get("BETBOT_SPORTRADAR_ODDS_API_VARIANT", "legacy_rowt1")
    ).strip().lower()
    if odds_api_variant not in {"legacy_rowt1", "prematch_v2"}:
        raise SportradarConfigurationError(
            "BETBOT_SPORTRADAR_ODDS_API_VARIANT must be "
            "legacy_rowt1 or prematch_v2"
        )
    settings = SportradarSettings(
        enabled=_bool(source, "BETBOT_SPORTRADAR_SHADOW_ENABLED", False),
        shadow_only=_bool(source, "BETBOT_SPORTRADAR_SHADOW_ONLY", True),
        api_key=str(source.get("SPORTRADAR_API_KEY", "")).strip(),
        access_level=access_level,
        language=language,
        poll_minutes=_int(
            source, "BETBOT_SPORTRADAR_POLL_MINUTES", 30, 15, 1440
        ),
        lookback_days=_int(
            source, "BETBOT_SPORTRADAR_LOOKBACK_DAYS", 1, 0, 14
        ),
        lookahead_days=_int(
            source, "BETBOT_SPORTRADAR_LOOKAHEAD_DAYS", 1, 0, 14
        ),
        request_timeout_seconds=_int(
            source, "BETBOT_SPORTRADAR_TIMEOUT_SECONDS", 20, 5, 60
        ),
        request_interval_seconds=_float(
            source, "BETBOT_SPORTRADAR_REQUEST_INTERVAL_SECONDS", 1.1, 1.0, 10.0
        ),
        maximum_retries=_int(
            source, "BETBOT_SPORTRADAR_MAX_RETRIES", 2, 0, 4
        ),
        odds_enabled=_bool(source, "BETBOT_SPORTRADAR_ODDS_ENABLED", True),
        odds_maximum_events_per_cycle=_int(
            source, "BETBOT_SPORTRADAR_ODDS_MAX_EVENTS_PER_CYCLE", 6, 0, 50
        ),
        odds_api_variant=odds_api_variant,
    )
    if settings.enabled and not settings.shadow_only:
        raise SportradarConfigurationError(
            "Sportradar v1 is shadow-only; BETBOT_SPORTRADAR_SHADOW_ONLY must remain enabled"
        )
    if settings.enabled and not settings.api_key:
        raise SportradarConfigurationError(
            "SPORTRADAR_API_KEY is required when Sportradar shadow is enabled"
        )
    return settings
