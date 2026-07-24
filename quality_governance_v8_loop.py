"""Single-owner autonomous quality loop — BetBot v11.

The filename is retained for deployment compatibility. All learning is owned
by AutonomousQualityOrchestrator; no legacy retraining process is started.
"""
from __future__ import annotations

import json
import time
from typing import Any

from autonomous_quality_orchestrator_v11 import AutonomousQualityOrchestrator
from runtime_health_v81 import QUALITY_SCHEMA, atomic_json, quality_health_path, utc_now
from settings_v81 import RuntimeSettings, load_settings


def build_components(settings: RuntimeSettings):
    return (AutonomousQualityOrchestrator(settings=settings),)


def run_cycle(orchestrator) -> dict[str, Any]:
    return orchestrator.run()


def _status(value: Any) -> str:
    return str(value.get("status", "UNKNOWN")) if isinstance(value, dict) else "UNKNOWN"


def main() -> None:
    settings = load_settings()
    (orchestrator,) = build_components(settings)
    health_path = quality_health_path()
    print(
        f"AUTONOMOUS QUALITY v11 START check={settings.governor_check_minutes}m "
        "owner=autonomous_quality_v11",
        flush=True,
    )
    while True:
        started = time.monotonic()
        cycle_started_at = utc_now()
        try:
            result = run_cycle(orchestrator)
            duration = round(time.monotonic() - started, 3)
            components = result.get("components", {})
            health = {
                "schema_version": QUALITY_SCHEMA,
                "status": "HEALTHY",
                "updated_at": utc_now(),
                "cycle_started_at": cycle_started_at,
                "cycle_duration_seconds": duration,
                "single_retraining_owner": True,
                "owner": "autonomous_quality_v11",
                "phase": result.get("phase", "UNKNOWN"),
                "next_action": result.get("next_action", ""),
                "fully_automatic_learning": result.get("fully_automatic_learning") is True,
                "components": {
                    name: _status(value)
                    for name, value in components.items()
                },
                "evidence_score": components.get("scorecard", {}).get("score", 0),
                "capital_stage": components.get("capital_governor", {}).get(
                    "current_stage", "SHADOW"
                ),
                "execution_allowed": components.get("capital_governor", {}).get(
                    "execution_allowed"
                ) is True,
                "source_history_modified": False,
            }
            atomic_json(health_path, health)
            print(
                json.dumps(
                    {"event": "AUTONOMOUS_QUALITY_CYCLE_COMPLETE", **health},
                    ensure_ascii=False,
                ),
                flush=True,
            )
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
            print(
                json.dumps(
                    {"event": "AUTONOMOUS_QUALITY_CYCLE_FAILED", **health},
                    ensure_ascii=False,
                ),
                flush=True,
            )
        time.sleep(settings.governor_check_minutes * 60)


if __name__ == "__main__":
    main()
