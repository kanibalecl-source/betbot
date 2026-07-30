import json
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from football_model_council import (
    COUNCIL_VERSION,
    FootballModelCouncil,
    bivariate_poisson_score_matrix,
    poisson_score_matrix,
    probability_from_score_matrix,
)
from football_model_council_trainer import train_football_council_shadow
from build_quality_training_from_history import _enforce_admission_ledger
from stage_b_model_layer import StageBModelLayer


class FootballModelCouncilTests(unittest.TestCase):
    def test_every_count_model_predicts_the_same_selected_market(self):
        for builder in (
            lambda: poisson_score_matrix(1.10, 0.60),
            lambda: bivariate_poisson_score_matrix(
                1.10, 0.60, shared_rate=0.08
            ),
        ):
            matrix = builder()
            over = probability_from_score_matrix(matrix, "OVER_2.5")
            under = probability_from_score_matrix(matrix, "UNDER_2.5")
            self.assertIsNotNone(over)
            self.assertIsNotNone(under)
            self.assertAlmostEqual(over + under, 1.0, places=8)

    def test_bivariate_model_is_not_a_duplicate_of_independent_poisson(self):
        independent = probability_from_score_matrix(
            poisson_score_matrix(1.50, 1.20), "DRAW"
        )
        bivariate = probability_from_score_matrix(
            bivariate_poisson_score_matrix(
                1.50, 1.20, shared_rate=0.20
            ),
            "DRAW",
        )
        self.assertNotAlmostEqual(independent, bivariate, places=5)

    def test_council_never_receives_decision_authority(self):
        with tempfile.TemporaryDirectory() as temporary:
            council = FootballModelCouncil(Path(temporary) / "missing.json")
            result = council.evaluate(
                champion_probability=0.63,
                market="UNDER_2.5",
                home_xg=1.10,
                away_xg=0.60,
                features={"league": "Test League"},
            )
        self.assertEqual(result.version, COUNCIL_VERSION)
        self.assertTrue(result.champion_remains_active)
        self.assertFalse(result.challengers_have_decision_authority)
        self.assertEqual(
            result.models["champion"]["probability"], 0.63
        )
        self.assertGreaterEqual(result.available_models, 5)
        self.assertFalse(result.bookmaker_used_as_model_input)

    def test_bookmaker_price_cannot_change_council_predictions(self):
        with tempfile.TemporaryDirectory() as temporary:
            council = FootballModelCouncil(Path(temporary) / "missing.json")
            common = {
                "champion_probability": 0.61,
                "market": "OVER_2.5",
                "home_xg": 1.55,
                "away_xg": 1.00,
            }
            first = council.evaluate(
                **common, features={"league": "L", "odds": 1.20}
            )
            second = council.evaluate(
                **common, features={"league": "L", "odds": 9.90}
            )
        self.assertEqual(
            first.diagnostic_consensus, second.diagnostic_consensus
        )
        self.assertEqual(first.models, second.models)

    def test_stage_b_preserves_legacy_probability_and_adds_council_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            layer = StageBModelLayer(
                FootballModelCouncil(Path(temporary) / "missing.json")
            )
            result = layer.enrich_pick(
                pick={},
                probability=0.7572,
                home_xg=1.10,
                away_xg=0.60,
                market="UNDER_2.5",
                council_features={"league": "L"},
            )
        self.assertAlmostEqual(result["advanced_market_prob"], 0.7572, places=3)
        self.assertEqual(result["football_council_mode"], "SHADOW_ONLY")
        self.assertFalse(result["football_council_decision_authority"])
        models = json.loads(result["football_council_models_json"])
        self.assertEqual(models["champion"]["probability"], 0.7572)

    def test_trainer_waits_without_touching_active_model(self):
        rows = [{
            "timestamp": "2026-01-01T00:00:00+00:00",
            "target": 1,
            "home_xg": 1.4,
            "away_xg": 0.8,
            "current_probability": 0.6,
            "market": "OVER_1.5",
            "league": "L",
        }]
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"BETBOT_COUNCIL_MIN_TRAINING_ROWS": "500"}
        ):
            result = train_football_council_shadow(rows, temporary)
            self.assertEqual(result["status"], "WAITING_FOR_SETTLED_DATA")
            self.assertFalse(result["active_model_modified"])
            self.assertFalse((Path(temporary) / "shadow_state.json").exists())

    def test_team_features_are_backward_compatible_with_old_admission_digest(self):
        row = {
            "record_id": "old-record",
            "source": "history.csv",
            "market": "OVER_2_5",
            "target": 1,
            "home_team": "Home",
            "away_team": "Away",
        }
        old_canonical = {
            "record_id": "old-record",
            "market": "OVER_2_5",
            "target": 1,
        }
        payload = json.dumps(
            old_canonical,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.sqlite3"
            connection = sqlite3.connect(ledger)
            connection.execute(
                "CREATE TABLE training_admission_ledger "
                "(record_id TEXT PRIMARY KEY,payload_sha256 TEXT NOT NULL,"
                "admitted_at TEXT NOT NULL,payload_json TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO training_admission_ledger VALUES (?,?,?,?)",
                ("old-record", digest, "2026-01-01T00:00:00Z", payload),
            )
            connection.commit()
            connection.close()
            quarantined = []
            accepted, conflicts = _enforce_admission_ledger(
                ledger, [row], quarantined
            )
        self.assertEqual(conflicts, 0)
        self.assertEqual(len(accepted), 1)
        self.assertFalse(quarantined)


if __name__ == "__main__":
    unittest.main()
