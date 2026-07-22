"""Fail-closed financial execution gate.

The current product generates recommendations only.  Any future bookmaker
adapter must call ``assert_execution_allowed`` immediately before submission.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


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
) -> None:
    if not betting_enabled():
        raise ExecutionBlocked("BETTING_ENABLED is false")
    if bankroll <= 0 or requested_stake <= 0:
        raise ExecutionBlocked("Invalid bankroll or stake")
    if not reconciliation_ok or execution_state_unknown:
        raise ExecutionBlocked("Reconciliation incomplete or execution state UNKNOWN")
    if not data_fresh or not audit_write_available:
        raise ExecutionBlocked("Fresh data and durable audit storage are required")
    if requested_stake > bankroll * limits.max_bet_fraction:
        raise ExecutionBlocked("Per-bet limit exceeded")
    if open_exposure + requested_stake > bankroll * limits.max_open_fraction:
        raise ExecutionBlocked("Open exposure limit exceeded")
    if fixture_exposure + requested_stake > bankroll * limits.max_fixture_fraction:
        raise ExecutionBlocked("Fixture exposure limit exceeded")
    if daily_pnl <= -(bankroll * limits.max_daily_loss_fraction):
        raise ExecutionBlocked("Daily loss limit reached")
    if drawdown_fraction >= limits.max_drawdown_fraction:
        raise ExecutionBlocked("Drawdown kill switch active")
