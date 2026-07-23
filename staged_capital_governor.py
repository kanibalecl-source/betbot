"""Staged Capital Governor v8.

The governor can only recommend or reduce capital stages.  Real-money stages
require an explicit external opt-in, a confirmed scorecard and fresh runtime
evidence.  It never sets BETTING_ENABLED and never submits a wager.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from storage_paths import get_data_dir
from settings_v81 import load_settings

STAGES = ("SHADOW", "PAPER", "CANARY", "LIMITED", "CONTROLLED")
REAL_STAGES = {"CANARY", "LIMITED", "CONTROLLED"}
STAGE_LIMITS = {
    "SHADOW": {"max_bet_fraction": 0.0, "max_open_fraction": 0.0, "max_daily_loss_fraction": 0.0, "max_drawdown_fraction": 0.0, "max_fixture_fraction": 0.0},
    "PAPER": {"max_bet_fraction": 0.0, "max_open_fraction": 0.0, "max_daily_loss_fraction": 0.0, "max_drawdown_fraction": 0.0, "max_fixture_fraction": 0.0},
    "CANARY": {"max_bet_fraction": 0.001, "max_open_fraction": 0.005, "max_daily_loss_fraction": 0.005, "max_drawdown_fraction": 0.03, "max_fixture_fraction": 0.001},
    "LIMITED": {"max_bet_fraction": 0.0015, "max_open_fraction": 0.01, "max_daily_loss_fraction": 0.0075, "max_drawdown_fraction": 0.04, "max_fixture_fraction": 0.0015},
    "CONTROLLED": {"max_bet_fraction": 0.0025, "max_open_fraction": 0.02, "max_daily_loss_fraction": 0.01, "max_drawdown_fraction": 0.05, "max_fixture_fraction": 0.0025},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _enabled(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return dict(value) if isinstance(value, Mapping) else {}
    except Exception:
        return {}


def _atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _append(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def evaluate_capital_stage(
    scorecard: Mapping[str, Any], runtime: Mapping[str, Any], current_stage: str,
    *, real_capital_opt_in: bool = False, maximum_runtime_age_seconds: int = 7200,
) -> dict[str, Any]:
    current = current_stage if current_stage in STAGES else "SHADOW"
    try:
        observed = datetime.fromisoformat(str(runtime.get("observed_at", "")).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        runtime_age = (datetime.now(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds()
    except (TypeError, ValueError):
        runtime_age = float("inf")
    runtime_gates = {
        "runtime_evidence_present": bool(runtime),
        "runtime_evidence_fresh": 0 <= runtime_age <= max(60, maximum_runtime_age_seconds),
        "reconciliation_ok": runtime.get("reconciliation_ok") is True,
        "durable_audit": runtime.get("audit_write_available") is True,
        "data_fresh": runtime.get("data_fresh") is True,
        "no_critical_incidents": int(runtime.get("critical_incidents", -1)) == 0,
    }
    evidence_confirmed = scorecard.get("status") == "STATISTICAL_EDGE_CONFIRMED"
    capital_evidence = scorecard.get("capital_readiness") == "EVIDENCE_READY"

    if not evidence_confirmed:
        recommended = "SHADOW"
    elif not capital_evidence:
        recommended = "PAPER"
    elif not all(runtime_gates.values()):
        recommended = "PAPER"
    else:
        settlements = max(0, int(runtime.get("canary_settlements", 0)))
        healthy_days = max(0, int(runtime.get("healthy_days", 0)))
        drawdown = max(0.0, float(runtime.get("drawdown_fraction", 0.0)))
        if settlements >= 500 and healthy_days >= 90 and drawdown < 0.03:
            recommended = "CONTROLLED"
        elif settlements >= 200 and healthy_days >= 30 and drawdown < 0.04:
            recommended = "LIMITED"
        else:
            recommended = "CANARY"

    # Real stages are impossible without a separate explicit operator opt-in.
    enforced = recommended
    if recommended in REAL_STAGES and not real_capital_opt_in:
        enforced = "PAPER"
    # Regressions are immediate; upward moves are one stage per successful run.
    if STAGES.index(enforced) > STAGES.index(current) + 1:
        enforced = STAGES[STAGES.index(current) + 1]
    if STAGES.index(recommended) < STAGES.index(current):
        enforced = recommended

    execution_allowed = enforced in REAL_STAGES and real_capital_opt_in
    return {
        "schema_version": "betbot.staged_capital_governor.v8",
        "version": 8,
        "updated_at": _now(),
        "status": "EXECUTION_ALLOWED" if execution_allowed else "FAIL_CLOSED",
        "current_stage": enforced,
        "recommended_stage": recommended,
        "execution_allowed": execution_allowed,
        "real_capital_opt_in": real_capital_opt_in,
        "scorecard_status": scorecard.get("status", "MISSING"),
        "capital_readiness": scorecard.get("capital_readiness", "NOT_READY"),
        "runtime_gates": runtime_gates,
        "runtime_evidence_age_seconds": round(runtime_age, 3) if runtime_age != float("inf") else None,
        "limits": STAGE_LIMITS[enforced],
        "advancement_policy": "one_stage_per_successful_evaluation",
        "regression_policy": "immediate_fail_closed",
        "betting_enabled_was_not_modified": True,
        "automatic_wager_submission": False,
        "source_history_modified": False,
    }


class StagedCapitalGovernor:
    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.root = Path(data_dir or get_data_dir()).resolve()
        self.work = self.root / "quality_retraining"
        self.scorecard_path = self.work / "statistical_evidence_scorecard_v8.json"
        self.runtime_path = self.work / "capital_runtime_evidence_v8.json"
        self.state_path = self.work / "staged_capital_governor_v8.json"
        self.events_path = self.work / "staged_capital_governor_events_v8.jsonl"

    def run(self) -> dict[str, Any]:
        settings = load_settings()
        previous = _read(self.state_path)
        result = evaluate_capital_stage(
            _read(self.scorecard_path),
            _read(self.runtime_path),
            str(previous.get("current_stage", "SHADOW")),
            real_capital_opt_in=settings.capital_real_enabled,
            maximum_runtime_age_seconds=settings.capital_runtime_max_age_seconds,
        )
        _atomic(self.state_path, result)
        _append(self.events_path, result)
        return result


def load_capital_policy(data_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or get_data_dir()).resolve()
    return _read(root / "quality_retraining" / "staged_capital_governor_v8.json")


if __name__ == "__main__":
    print(json.dumps(StagedCapitalGovernor().run(), ensure_ascii=False, indent=2))
