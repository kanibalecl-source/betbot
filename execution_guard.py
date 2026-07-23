"""Fail-closed financial execution gate.

The current product generates recommendations only.  Any future bookmaker
adapter must call ``assert_execution_allowed`` immediately before submission.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from staged_capital_governor import REAL_STAGES, load_capital_policy


@dataclass(frozen=True)
class ExecutionLimits:
    max_bet_fraction: float = 0.0025
    max_open_fraction: float = 0.02
    max_daily_loss_fraction: float = 0.01
    max_drawdown_fraction: float = 0.05
    max_fixture_fraction: float = 0.0025


class ExecutionBlocked(RuntimeError):
    pass


def betting_enabled() -> bool:
    return os.getenv("BETTING_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def assert_execution_allowed(
    *,
    bankroll: float,
    requested_stake: float,
    open_exposure: float,
    fixture_exposure: float,
    daily_pnl: float,
    drawdown_fraction: float,
    reconciliation_ok: bool,
    data_fresh: bool,
    audit_write_available: bool,
    execution_state_unknown: bool = False,
    limits: ExecutionLimits = ExecutionLimits(),
    capital_policy: Mapping[str, Any] | None = None,
) -> None:
    if not betting_enabled():
        raise ExecutionBlocked("BETTING_ENABLED is false")
    if bankroll <= 0 or requested_stake <= 0:
        raise ExecutionBlocked("Invalid bankroll or stake")
    if not reconciliation_ok or execution_state_unknown:
        raise ExecutionBlocked("Reconciliation incomplete or execution state UNKNOWN")
    if not data_fresh or not audit_write_available:
        raise ExecutionBlocked("Fresh data and durable audit storage are required")
    policy = dict(capital_policy) if capital_policy is not None else load_capital_policy()
    if not policy or policy.get("execution_allowed") is not True:
        raise ExecutionBlocked("Staged Capital Governor has not allowed execution")
    if policy.get("current_stage") not in REAL_STAGES:
        raise ExecutionBlocked("Capital stage is not authorized for real execution")
    try:
        updated = datetime.fromisoformat(str(policy.get("updated_at", "")).replace("Z", "+00:00"))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - updated.astimezone(timezone.utc)).total_seconds()
    except (TypeError, ValueError):
        age = float("inf")
    maximum_age = max(60, int(os.getenv("BETBOT_CAPITAL_POLICY_MAX_AGE_SECONDS", "7200")))
    if age < 0 or age > maximum_age:
        raise ExecutionBlocked("Capital policy is missing or stale")
    stage = policy.get("limits", {}) if isinstance(policy.get("limits"), Mapping) else {}
    effective = ExecutionLimits(
        max_bet_fraction=min(limits.max_bet_fraction, float(stage.get("max_bet_fraction", 0.0))),
        max_open_fraction=min(limits.max_open_fraction, float(stage.get("max_open_fraction", 0.0))),
        max_daily_loss_fraction=min(limits.max_daily_loss_fraction, float(stage.get("max_daily_loss_fraction", 0.0))),
        max_drawdown_fraction=min(limits.max_drawdown_fraction, float(stage.get("max_drawdown_fraction", 0.0))),
        max_fixture_fraction=min(limits.max_fixture_fraction, float(stage.get("max_fixture_fraction", 0.0))),
    )
    if requested_stake > bankroll * effective.max_bet_fraction:
        raise ExecutionBlocked("Per-bet limit exceeded")
    if open_exposure + requested_stake > bankroll * effective.max_open_fraction:
        raise ExecutionBlocked("Open exposure limit exceeded")
    if fixture_exposure + requested_stake > bankroll * effective.max_fixture_fraction:
        raise ExecutionBlocked("Fixture exposure limit exceeded")
    if daily_pnl <= -(bankroll * effective.max_daily_loss_fraction):
        raise ExecutionBlocked("Daily loss limit reached")
    if drawdown_fraction >= effective.max_drawdown_fraction:
        raise ExecutionBlocked("Drawdown kill switch active")
