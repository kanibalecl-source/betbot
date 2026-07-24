import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import autonomous_learning_governor as governor_module
import quality_model_registry as registry


class AutonomousLearningGovernorTests(unittest.TestCase):
    def _candidate(self, root: Path) -> Path:
        path = root / "quality_retraining" / "quality_shadow_state.candidate.latest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "status": "TRAINED_TIME_SAFE",
            "candidate_path": "candidate-v7.json",
            "active_model_was_not_modified": True,
            "validation": {"status": "POSITIVE_VALIDATION_MANUAL_APPROVAL"},
        }), encoding="utf-8")
        return path

    def _guardian(self, root: Path, healthy: bool = True) -> None:
        path = root / "quality_retraining" / "data_quality_guardian.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "status": "HEALTHY" if healthy else "ATTENTION",
            "alerts": [] if healthy else [{"severity": "WARNING", "code": "TEST"}],
            "training_readiness": {"ready_for_validation": healthy},
        }), encoding="utf-8")

    def _scorecard(self, root: Path, candidate: Path) -> None:
        path = root / "quality_retraining" / "statistical_evidence_scorecard_v8.json"
        path.write_text(json.dumps({
            "status": "STATISTICAL_EDGE_CONFIRMED",
            "confirmed_statistical_edge": True,
            "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
        }), encoding="utf-8")

    def _live(self, settled: int = 300):
        return {
            "status": "POSITIVE_LIVE_SHADOW_MANUAL_APPROVAL",
            "settled_samples": settled,
            "candidate_id": "candidate-v7.json",
        }

    def test_disabled_governor_never_changes_model(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            result = governor_module.AutonomousLearningGovernor(folder).run()
            self.assertEqual(result["status"], "DISABLED")
            self.assertFalse(result["automatic_model_change"])

    def test_all_gates_start_canary_without_promotion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            candidate = self._candidate(root)
            self._guardian(root)
            self._scorecard(root, candidate)
            with patch.dict(os.environ, {"BETBOT_AUTONOMOUS_GOVERNOR_ENABLED": "1"}, clear=True), patch.object(
                governor_module, "live_shadow_report", return_value=self._live()
            ), patch.object(governor_module, "promote_candidate_automatically") as promote:
                result = governor_module.AutonomousLearningGovernor(root).run()
            self.assertEqual(result["status"], "CANARY_STARTED")
            self.assertEqual(result["canary_percent"], 10)
            self.assertFalse(result["automatic_model_change"])
            promote.assert_not_called()

    def test_canary_requires_fresh_future_settlements_then_promotes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            candidate = self._candidate(root)
            self._guardian(root)
            self._scorecard(root, candidate)
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            env = {
                "BETBOT_AUTONOMOUS_GOVERNOR_ENABLED": "1",
                "BETBOT_GOVERNOR_CANARY_25_NEW_SAMPLES": "2",
                "BETBOT_GOVERNOR_CANARY_50_NEW_SAMPLES": "4",
                "BETBOT_GOVERNOR_CANARY_100_NEW_SAMPLES": "6",
            }
            reports = [self._live(300), self._live(301), self._live(302), self._live(304), self._live(306)]
            with patch.dict(os.environ, env, clear=True), patch.object(
                governor_module, "live_shadow_report", side_effect=reports
            ), patch.object(
                governor_module,
                "promote_candidate_automatically",
                return_value={
                    "status": "PROMOTED_AUTONOMOUSLY",
                    "active_sha256": "active-v7-hash",
                    "previous_backup": str(root / "quality_retraining" / "registry" / "old.json"),
                },
            ) as promote:
                service = governor_module.AutonomousLearningGovernor(root)
                self.assertEqual(service.run()["status"], "CANARY_STARTED")
                self.assertEqual(service.run()["canary_percent"], 10)
                self.assertEqual(service.run()["canary_percent"], 25)
                self.assertEqual(service.run()["canary_percent"], 50)
                result = service.run()
            self.assertEqual(result["status"], "PROMOTED_AUTONOMOUSLY")
            promote.assert_called_once_with(digest, root.resolve())

    def test_unhealthy_guardian_blocks_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            candidate = self._candidate(root)
            self._guardian(root, healthy=False)
            self._scorecard(root, candidate)
            with patch.dict(os.environ, {"BETBOT_AUTONOMOUS_GOVERNOR_ENABLED": "1"}, clear=True), patch.object(
                governor_module, "live_shadow_report", return_value=self._live()
            ):
                result = governor_module.AutonomousLearningGovernor(root).run()
            self.assertEqual(result["status"], "WAITING_FOR_ALL_GATES")
            self.assertFalse(result["gates"]["guardian_healthy_and_ready"])


class AutomaticRegistryTests(unittest.TestCase):
    def _files(self, root: Path) -> tuple[Path, Path]:
        active = root / "quality_shadow_state.json"
        active.write_text(json.dumps({"version": "champion"}), encoding="utf-8")
        candidate = root / "quality_retraining" / "quality_shadow_state.candidate.latest.json"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(json.dumps({
            "version": "challenger",
            "candidate_path": "candidate-v7.json",
            "active_model_was_not_modified": True,
            "validation": {"status": "POSITIVE_VALIDATION_MANUAL_APPROVAL"},
        }), encoding="utf-8")
        return active, candidate

    def _scorecard(self, root: Path, candidate: Path) -> None:
        (root / "quality_retraining" / "statistical_evidence_scorecard_v8.json").write_text(
            json.dumps({
                "status": "STATISTICAL_EDGE_CONFIRMED",
                "confirmed_statistical_edge": True,
                "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
            }),
            encoding="utf-8",
        )

    def test_automatic_registry_is_disabled_by_default(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            root = Path(folder)
            active, candidate = self._files(root)
            self._scorecard(root, candidate)
            before = active.read_bytes()
            result = registry.promote_candidate_automatically(
                hashlib.sha256(candidate.read_bytes()).hexdigest(), root
            )
            self.assertEqual(result["status"], "REFUSED_AUTONOMOUS_PROMOTION_DISABLED")
            self.assertEqual(active.read_bytes(), before)

    def test_automatic_registry_rechecks_identity_and_two_gates(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            active, candidate = self._files(root)
            self._scorecard(root, candidate)
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            live = {"status": "POSITIVE_LIVE_SHADOW_MANUAL_APPROVAL"}
            with patch.dict(os.environ, {"BETBOT_AUTONOMOUS_PROMOTION_ENABLED": "1"}, clear=True), patch.object(
                registry, "live_shadow_report", return_value=live
            ):
                refused = registry.promote_candidate_automatically("wrong", root)
                promoted = registry.promote_candidate_automatically(digest, root)
            self.assertEqual(refused["status"], "REFUSED_CANDIDATE_CHANGED")
            self.assertEqual(promoted["status"], "PROMOTED_AUTONOMOUSLY")
            self.assertEqual(json.loads(active.read_text(encoding="utf-8"))["version"], "challenger")
            self.assertTrue(Path(promoted["previous_backup"]).is_file())


if __name__ == "__main__":
    unittest.main()
