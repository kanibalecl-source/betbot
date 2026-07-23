"""Typed, secret-free runtime configuration for Architecture Hardening v8.1."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from typing import Mapping


class ConfigurationError(RuntimeError):
    pass


def _bool(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = str(env.get(name, "1" if default else "0")).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean")


def _int(env: Mapping[str, str], name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(env.get(name, default)).strip())
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return value


def _float(env: Mapping[str, str], name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(str(env.get(name, default)).strip())
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} must be numeric") from exc
    if not minimum <= value <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True)
class RuntimeSettings:
    schema_version: str
    port: int
    heartbeat_seconds: int
    governor_check_minutes: int
    quality_retrain_min_new_rows: int
    quality_retrain_min_hours: int
    evidence_min_oos_samples: int
    evidence_min_clv_samples: int
    evidence_min_segment_samples: int
    evidence_max_ece: float
    capital_policy_max_age_seconds: int
    capital_runtime_max_age_seconds: int
    betting_enabled: bool
    capital_real_enabled: bool
    autonomous_governor_enabled: bool
    autonomous_promotion_enabled: bool
    volleyball_enabled: bool
    volleyball_shadow_only: bool
    volleyball_poll_minutes: int
    volleyball_backfill_days: int

    def public_snapshot(self) -> dict[str, object]:
        return asdict(self)

    def fingerprint(self) -> str:
        encoded = json.dumps(self.public_snapshot(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_settings(
    env: Mapping[str, str] | None = None, *, validate_cross_fields: bool = True
) -> RuntimeSettings:
    source = os.environ if env is None else env
    settings = RuntimeSettings(
        schema_version="betbot.runtime_settings.v8.1",
        port=_int(source, "PORT", 8080, 1, 65535),
        heartbeat_seconds=_int(source, "BETBOT_HEARTBEAT_SECONDS", 30, 10, 300),
        governor_check_minutes=_int(source, "BETBOT_GOVERNOR_CHECK_MINUTES", 60, 15, 1440),
        quality_retrain_min_new_rows=_int(source, "BETBOT_QUALITY_RETRAIN_MIN_NEW_ROWS", 300, 1, 1000000),
        quality_retrain_min_hours=_int(source, "BETBOT_QUALITY_RETRAIN_MIN_HOURS", 24, 1, 8760),
        evidence_min_oos_samples=_int(source, "BETBOT_EVIDENCE_MIN_OOS_SAMPLES", 1000, 100, 10000000),
        evidence_min_clv_samples=_int(source, "BETBOT_EVIDENCE_MIN_CLV_SAMPLES", 200, 50, 10000000),
        evidence_min_segment_samples=_int(source, "BETBOT_EVIDENCE_MIN_SEGMENT_SAMPLES", 250, 50, 1000000),
        evidence_max_ece=_float(source, "BETBOT_EVIDENCE_MAX_ECE", 0.05, 0.001, 0.25),
        capital_policy_max_age_seconds=_int(source, "BETBOT_CAPITAL_POLICY_MAX_AGE_SECONDS", 7200, 60, 86400),
        capital_runtime_max_age_seconds=_int(source, "BETBOT_CAPITAL_RUNTIME_MAX_AGE_SECONDS", 7200, 60, 86400),
        betting_enabled=_bool(source, "BETTING_ENABLED", False),
        capital_real_enabled=_bool(source, "BETBOT_CAPITAL_REAL_ENABLED", False),
        autonomous_governor_enabled=_bool(source, "BETBOT_AUTONOMOUS_GOVERNOR_ENABLED", False),
        autonomous_promotion_enabled=_bool(source, "BETBOT_AUTONOMOUS_PROMOTION_ENABLED", False),
        volleyball_enabled=_bool(source, "BETBOT_VOLLEYBALL_ENABLED", False),
        volleyball_shadow_only=_bool(source, "BETBOT_VOLLEYBALL_SHADOW_ONLY", True),
        volleyball_poll_minutes=_int(
            source, "BETBOT_VOLLEYBALL_POLL_MINUTES", 15, 5, 1440
        ),
        volleyball_backfill_days=_int(
            source, "BETBOT_VOLLEYBALL_BACKFILL_DAYS", 30, 0, 365
        ),
    )
    if validate_cross_fields and settings.betting_enabled and not settings.capital_real_enabled:
        raise ConfigurationError(
            "BETTING_ENABLED=true requires BETBOT_CAPITAL_REAL_ENABLED=1; startup blocked"
        )
    if validate_cross_fields and settings.autonomous_promotion_enabled and not settings.autonomous_governor_enabled:
        raise ConfigurationError(
            "Autonomous promotion requires BETBOT_AUTONOMOUS_GOVERNOR_ENABLED=1"
        )
    if validate_cross_fields and settings.evidence_min_clv_samples > settings.evidence_min_oos_samples:
        raise ConfigurationError(
            "BETBOT_EVIDENCE_MIN_CLV_SAMPLES cannot exceed BETBOT_EVIDENCE_MIN_OOS_SAMPLES"
        )
    if validate_cross_fields and settings.volleyball_enabled and not settings.volleyball_shadow_only:
        raise ConfigurationError(
            "Volleyball v9.0 is shadow-only; BETBOT_VOLLEYBALL_SHADOW_ONLY must remain enabled"
        )
    return settings
