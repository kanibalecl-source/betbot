from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from autonomous_quality_orchestrator_v11 import (
    AutonomousQualityOrchestrator,
    readiness_from_guardian,
)
from settings_v81 import load_settings


class Component:
    def __init__(self, status: str):
        self.status = status
        self.calls = 0

    def run(self):
        self.calls += 1
        if self.status == "SCORE":
            return {
                "status": "COLLECTING",
                "confirmed_statistical_edge": False,
                "score": 4,
            }
        if self.status == "CAPITAL":
            return {"status": "FAIL_CLOSED", "current_stage": "SHADOW"}
        return {"status": self.status}


class AutonomousQualityV11Tests(unittest.TestCase):
    def test_readiness_requires_all_quality_gates(self):
        report = {
            "status": "HEALTHY",
            "alerts": [],
            "metrics": {
                "settlement_coverage": 0.98,
                "closing_odds_coverage": 0.85,
            },
            "training_readiness": {
                "settled": 400,
                "ready_for_validation": True,
            },
        }
        ready = readiness_from_guardian(
            report,
            minimum_settled=300,
            minimum_settlement_coverage=0.95,
            minimum_closing_coverage=0.80,
        )
        self.assertTrue(ready["ready"])
        report["metrics"]["closing_odds_coverage"] = 0.50
        blocked = readiness_from_guardian(
            report,
            minimum_settled=300,
            minimum_settlement_coverage=0.95,
            minimum_closing_coverage=0.80,
        )
        self.assertFalse(blocked["ready"])

    def test_orchestrator_does_not_train_on_insufficient_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            work = root / "quality_retraining"
            work.mkdir(parents=True)

            def guardian_runner(_):
                (work / "data_quality_guardian.json").write_text(
                    json.dumps({
                        "status": "ATTENTION",
                        "alerts": [{"severity": "WARNING"}],
                        "metrics": {
                            "settlement_coverage": 0.50,
                            "closing_odds_coverage": 0.20,
                        },
                        "training_readiness": {
                            "settled": 12,
                            "ready_for_validation": False,
                        },
                    }),
                    encoding="utf-8",
                )
                return {"status": "ATTENTION"}

            retrainer = Component("CANDIDATE_CREATED")
            service = AutonomousQualityOrchestrator(
                root,
                settings=load_settings({
                    "BETBOT_AUTONOMOUS_GOVERNOR_ENABLED": "1",
                    "BETBOT_AUTONOMOUS_PROMOTION_ENABLED": "1",
                }),
                guardian_runner=guardian_runner,
                retrainer=retrainer,
                scorecard=Component("SCORE"),
                model_governor=Component("WAITING_FOR_ALL_GATES"),
                capital_governor=Component("CAPITAL"),
            )
            result = service.run()
            self.assertEqual(retrainer.calls, 0)
            self.assertEqual(result["phase"], "COLLECTING_QUALITY_DATA")
            self.assertFalse(result["source_history_modified"])
            self.assertTrue((work / "autonomy_v11_state.json").is_file())

    def test_ready_cycle_runs_components_in_safe_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            work = root / "quality_retraining"
            work.mkdir(parents=True)
            calls = []

            def guardian_runner(_):
                calls.append("guardian")
                (work / "data_quality_guardian.json").write_text(
                    json.dumps({
                        "status": "HEALTHY",
                        "alerts": [],
                        "metrics": {
                            "settlement_coverage": 0.99,
                            "closing_odds_coverage": 0.90,
                        },
                        "training_readiness": {
                            "settled": 1200,
                            "ready_for_validation": True,
                        },
                    }),
                    encoding="utf-8",
                )
                return {"status": "HEALTHY"}

            class Ordered:
                def __init__(self, name, response):
                    self.name = name
                    self.response = response

                def run(self):
                    calls.append(self.name)
                    return self.response

            service = AutonomousQualityOrchestrator(
                root,
                settings=load_settings({
                    "BETBOT_AUTONOMOUS_GOVERNOR_ENABLED": "1",
                    "BETBOT_AUTONOMOUS_PROMOTION_ENABLED": "1",
                }),
                guardian_runner=guardian_runner,
                retrainer=Ordered("retrainer", {"status": "CANDIDATE_CREATED"}),
                scorecard=Ordered("scorecard", {
                    "status": "STATISTICAL_EDGE_CONFIRMED",
                    "confirmed_statistical_edge": True,
                    "score": 10,
                }),
                model_governor=Ordered("governor", {"status": "CANARY_STARTED"}),
                capital_governor=Ordered("capital", {
                    "status": "FAIL_CLOSED",
                    "current_stage": "PAPER",
                }),
            )
            result = service.run()
            self.assertEqual(
                calls,
                ["guardian", "retrainer", "scorecard", "governor", "capital"],
            )
            self.assertEqual(result["phase"], "AUTONOMOUS_CANARY")
            self.assertTrue(result["fully_automatic_learning"])


if __name__ == "__main__":
    unittest.main()
