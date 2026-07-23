"""Single-owner quality governance loop — Architecture Hardening v8.1."""
from __future__ import annotations

import json
import time
from typing import Any

from autonomous_learning_governor import AutonomousLearningGovernor
from quality_auto_retraining import ControlledQualityRetrainer
from runtime_health_v81 import QUALITY_SCHEMA, atomic_json, quality_health_path, utc_now
from settings_v81 import RuntimeSettings, load_settings
from staged_capital_governor import StagedCapitalGovernor
from statistical_evidence_scorecard import StatisticalEvidenceScorecard


def build_components(settings: RuntimeSettings):
    return (
        ControlledQualityRetrainer(
            min_new_rows=settings.quality_retrain_min_new_rows,
            min_hours=settings.quality_retrain_min_hours,
        ),
        AutonomousLearningGovernor(),
        StatisticalEvidenceScorecard(),
        StagedCapitalGovernor(),
    )


def run_cycle(retrainer, model_governor, scorecard, capital_governor) -> dict[str, Any]:
    return {
        "retraining": retrainer.run(),
        "model_governor": model_governor.run(),
        "evidence_scorecard": scorecard.run(),
        "capital_governor": capital_governor.run(),
    }


def _status(value: Any) -> str:
    return str(value.get("status", "UNKNOWN")) if isinstance(value, dict) else "UNKNOWN"


def main() -> None:
    settings = load_settings()
    retrainer, model_governor, scorecard, capital_governor = build_components(settings)
    health_path = quality_health_path()
    print(
        f"QUALITY GOVERNANCE v8.1 START check={settings.governor_check_minutes}m "
        f"owner=quality_governance_v8",
        flush=True,
    )
    while True:
        started = time.monotonic()
        cycle_started_at = utc_now()
        try:
            result = run_cycle(retrainer, model_governor, scorecard, capital_governor)
            duration = round(time.monotonic() - started, 3)
            health = {
                "schema_version": QUALITY_SCHEMA,
                "status": "HEALTHY",
                "updated_at": utc_now(),
                "cycle_started_at": cycle_started_at,
                "cycle_duration_seconds": duration,
                "single_retraining_owner": True,
                "components": {
                    "retraining": _status(result["retraining"]),
                    "model_governor": _status(result["model_governor"]),
                    "evidence_scorecard": _status(result["evidence_scorecard"]),
                    "capital_governor": _status(result["capital_governor"]),
                },
                "evidence_score": result["evidence_scorecard"].get("score", 0),
                "capital_stage": result["capital_governor"].get("current_stage", "SHADOW"),
                "execution_allowed": result["capital_governor"].get("execution_allowed") is True,
                "source_history_modified": False,
            }
            atomic_json(health_path, health)
            print(json.dumps({"event": "QUALITY_CYCLE_COMPLETE", **health}, ensure_ascii=False), flush=True)
        except Exception as exc:
            health = {
                "schema_version": QUALITY_SCHEMA,
                "status": "FAILED",
                "updated_at": utc_now(),
                "cycle_started_at": cycle_started_at,
                "cycle_duration_seconds": round(time.monotonic() - started, 3),
                "error_type": type(exc).__name__,
                "error": str(exc)[:500],
                "execution_allowed": False,
                "source_history_modified": False,
            }
            atomic_json(health_path, health)
            print(json.dumps({"event": "QUALITY_CYCLE_FAILED", **health}, ensure_ascii=False), flush=True)
        time.sleep(settings.governor_check_minutes * 60)


if __name__ == "__main__":
    main()
