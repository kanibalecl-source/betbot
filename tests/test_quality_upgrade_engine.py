import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.safe_upgrades.shadow_mode import assess_shadow, write_shadow_event
from quality_upgrade_engine import (
    BetaCalibrator,
    DixonColesEngine,
    assess_quality,
    learn_stacking_weights,
    no_vig_probabilities,
    portfolio_fractional_kelly,
    probability_drift_report,
    train_time_safe_state,
)


class QualityUpgradeTests(unittest.TestCase):
    def test_power_devig_is_normalized(self):
        result = no_vig_probabilities({"1": 2.10, "X": 3.45, "2": 3.55})
        self.assertAlmostEqual(sum(result.values()), 1.0, places=7)
        self.assertTrue(all(0 < value < 1 for value in result.values()))

    def test_dixon_coles_score_matrix_is_normalized(self):
        engine = DixonColesEngine(rho=-0.08)
        matrix = engine.score_matrix(1.55, 1.10)
        self.assertAlmostEqual(sum(matrix.values()), 1.0, places=8)
        self.assertGreater(matrix[(1, 1)], 0)

    def test_market_pairs_are_complements(self):
        markets = DixonColesEngine().market_probabilities(1.45, 1.05)
        self.assertAlmostEqual(markets["BTTS_YES"] + markets["BTTS_NO"], 1.0, places=6)
        self.assertAlmostEqual(markets["OVER_2_5"] + markets["UNDER_2_5"], 1.0, places=6)
        self.assertAlmostEqual(
            markets["HOME_WIN"] + markets["DRAW"] + markets["AWAY_WIN"], 1.0, places=6
        )

    def test_server_market_aliases_are_supported(self):
        engine = DixonColesEngine()
        self.assertIsNotNone(engine.predict_market("DOUBLE_1X", 1.45, 1.05))
        self.assertIsNotNone(engine.predict_market("DOUBLE_X2", 1.45, 1.05))
        self.assertIsNotNone(engine.predict_market("DOUBLE_12", 1.45, 1.05))
        self.assertIsNotNone(engine.predict_market("OVER_0.5", 1.45, 1.05))
        self.assertIsNotNone(engine.predict_market("UNDER_4.5", 1.45, 1.05))

    def test_stacker_learns_more_reliable_model(self):
        targets = [0, 0, 1, 1] * 15
        rows = []
        for target in targets:
            good = 0.85 if target else 0.15
            bad = 0.20 if target else 0.80
            rows.append([good, bad, 0.50])
        weights = learn_stacking_weights(rows, targets)
        self.assertAlmostEqual(sum(weights), 1.0, places=6)
        self.assertGreater(weights[0], weights[1])
        self.assertGreater(weights[0], weights[2])

    def test_beta_calibrator_stays_in_probability_range(self):
        probabilities = [0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85] * 3
        targets = [0, 0, 0, 0, 1, 1, 1, 1] * 3
        calibrator = BetaCalibrator().fit(probabilities, targets)
        self.assertTrue(0.0 < calibrator.predict(0.2) < 1.0)
        self.assertTrue(0.0 < calibrator.predict(0.8) < 1.0)
        self.assertLess(calibrator.predict(0.2), calibrator.predict(0.8))

    def test_quality_assessment_does_not_mutate_current_output(self):
        raw = {
            "home_xg": 1.65,
            "away_xg": 0.95,
            "market": "HOME_WIN",
            "market_odds": {"HOME_WIN": 1.95, "DRAW": 3.50, "AWAY_WIN": 4.20},
            "odds": 1.95,
            "data_quality": 0.90,
        }
        current = {"market": "HOME_WIN", "probability": 0.61, "bookmaker_odds": 1.95}
        before = dict(current)
        result = assess_quality(raw, current)
        self.assertEqual(current, before)
        self.assertIsNotNone(result.dixon_coles_probability)
        self.assertIsNotNone(result.market_probability_no_vig)
        self.assertIn(result.decision, {"ACCEPT", "REVIEW", "PASS"})

    def test_time_safe_training_uses_three_distinct_partitions(self):
        rows = []
        for index in range(60):
            target = 1 if index % 3 else 0
            rows.append({
                "current_probability": 0.70 if target else 0.30,
                "dixon_coles_probability": 0.66 if target else 0.34,
                "market_probability": 0.58 if target else 0.42,
                "target": target,
            })
        state = train_time_safe_state(rows)
        self.assertEqual(state["status"], "TRAINED_TIME_SAFE")
        self.assertEqual(sum(state["split"].values()), 60)
        self.assertGreater(state["split"]["holdout"], 0)
        self.assertIn("brier_score", state["holdout_metrics"])

    def test_shadow_event_contains_new_quality_diagnostics(self):
        raw = {
            "league": "Test League",
            "home_xg": 1.5,
            "away_xg": 1.0,
            "odds": 2.0,
            "market_odds": {"HOME_WIN": 2.0, "DRAW": 3.4, "AWAY_WIN": 3.9},
        }
        current = {
            "match_name": "Home vs Away",
            "market": "HOME_WIN",
            "probability": 0.57,
            "edge": 0.14,
            "confidence": 57,
            "risk_level": "MEDIUM",
            "recommendation": "BET",
            "bookmaker_odds": 2.0,
        }
        assessment = assess_shadow(raw, current)
        self.assertEqual(assessment.mode, "shadow_only_no_runtime_effect")
        self.assertIn("conservative_probability", assessment.quality_upgrade)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "shadow.jsonl"
            write_shadow_event(assessment, str(path))
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("quality_upgrade", payload)

    def test_probability_drift_detects_large_shift(self):
        reference = [0.35 + (index % 10) * 0.01 for index in range(100)]
        current = [0.72 + (index % 10) * 0.01 for index in range(100)]
        report = probability_drift_report(reference, current)
        self.assertEqual(report["status"], "DRIFT_ALERT")
        self.assertGreater(report["psi"], 0.25)

    def test_portfolio_kelly_respects_total_and_group_caps(self):
        candidates = [
            {"match_id": "A", "probability": 0.65, "odds": 2.0, "pick": "HOME"},
            {"match_id": "A", "probability": 0.62, "odds": 2.1, "pick": "OVER"},
            {"match_id": "B", "probability": 0.64, "odds": 2.0, "pick": "BTTS"},
            {"match_id": "C", "probability": 0.63, "odds": 2.0, "pick": "AWAY"},
        ]
        allocations = portfolio_fractional_kelly(candidates, bankroll=1000)
        self.assertLessEqual(sum(row["stake_fraction"] for row in allocations), 0.06)
        group_a = sum(
            row["stake_fraction"] for row in allocations if row["match_id"] == "A"
        )
        self.assertLessEqual(group_a, 0.03)

    def test_enabling_shadow_does_not_change_master_engine_decision(self):
        from master_prediction_engine import MasterPredictionEngine
        request = {
            "home": "Home",
            "away": "Away",
            "league": "Test",
            "market": "OVER_2_5",
            "odds": 1.95,
            "probability": 0.61,
            "home_xg": 1.55,
            "away_xg": 1.10,
        }
        with tempfile.TemporaryDirectory() as folder:
            log = str(Path(folder) / "events.jsonl")
            with patch.dict(os.environ, {"BETBOT_QUALITY_SHADOW": "0"}, clear=False):
                baseline = MasterPredictionEngine().process_match(request)
            with patch.dict(
                os.environ,
                {"BETBOT_QUALITY_SHADOW": "1", "BETBOT_SHADOW_LOG": log},
                clear=False,
            ):
                shadow = MasterPredictionEngine().process_match(request)
            baseline.pop("timestamp")
            shadow.pop("timestamp")
            self.assertEqual(baseline, shadow)
            self.assertTrue(Path(log).exists())

    def test_master_engine_preserves_production_missing_probability_rejection(self):
        from master_prediction_engine import MasterPredictionEngine
        result = MasterPredictionEngine().process_match({
            "home": "Home", "away": "Away", "market": "OVER_2_5", "odds": 1.95,
            "home_xg": 1.55, "away_xg": 1.10,
        })
        self.assertEqual(result["filter_status"], "REJECTED")
        self.assertEqual(result["filter_reason"], "MISSING_VERIFIED_MARKET_PROBABILITY")
        self.assertIsNone(result["probability"])


if __name__ == "__main__":
    unittest.main()
