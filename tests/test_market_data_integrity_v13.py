from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import data_api
from market_data_integrity_v13 import build_market_consensus
from market_integrity_audit_v13 import (
    MarketIntegrityAuditV13,
    _evaluate,
    sport_training_ready,
)


NOW = "2026-07-26T12:00:00+00:00"


def quote(bookmaker, outcome, odds, observed_at=NOW):
    return {
        "bookmaker": bookmaker,
        "market": "TOTAL_1.5",
        "outcome": outcome,
        "odds": odds,
        "observed_at": observed_at,
    }


class MarketConsensusV13Tests(unittest.TestCase):
    def test_complete_two_book_market_passes(self):
        rows = [
            quote("Superbet", "OVER", 1.80), quote("Superbet", "UNDER", 2.05),
            quote("STS", "OVER", 1.85), quote("STS", "UNDER", 2.00),
        ]
        result = build_market_consensus(
            rows,
            sport="football",
            market="TOTAL_1.5",
            required_outcomes=("OVER", "UNDER"),
            bookmaker_allowlist=("Superbet", "STS"),
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["bookmaker_count"], 2)
        self.assertTrue(result["consensus_id"])

    def test_incomplete_bookmaker_markets_fail_closed(self):
        rows = [quote("Superbet", "OVER", 1.80), quote("STS", "OVER", 1.85)]
        result = build_market_consensus(
            rows,
            sport="football",
            market="TOTAL_1.5",
            required_outcomes=("OVER", "UNDER"),
        )
        self.assertNotEqual(result["status"], "PASS")

    def test_non_allowlisted_bookmaker_is_rejected(self):
        rows = [
            quote("Offshore", "OVER", 1.80), quote("Offshore", "UNDER", 2.05),
            quote("STS", "OVER", 1.85), quote("STS", "UNDER", 2.00),
        ]
        result = build_market_consensus(
            rows,
            sport="football",
            market="TOTAL_1.5",
            required_outcomes=("OVER", "UNDER"),
            bookmaker_allowlist=("Superbet", "STS"),
        )
        self.assertNotEqual(result["status"], "PASS")
        self.assertGreater(result["rejected"].get("bookmaker_not_allowed", 0), 0)


class FootballPublicationConsensusTests(unittest.TestCase):
    @staticmethod
    def _row(bookmaker, bookmaker_id, market, odds):
        return {
            "bookmaker": bookmaker,
            "bookmaker_id": bookmaker_id,
            "market": market,
            "odds": odds,
            "observed_at": NOW,
            "bet_id": 5,
            "bet_name": "Goals Over/Under",
        }

    def test_two_source_consensus_can_publish_one_polish_bookmaker(self):
        rows = [
            self._row("Superbet", 10, "OVER_1.5", 1.80),
            self._row("Superbet", 10, "UNDER_1.5", 2.05),
            self._row("Pinnacle", 20, "OVER_1.5", 1.85),
            self._row("Pinnacle", 20, "UNDER_1.5", 2.00),
        ]
        with patch.object(data_api, "_iter_fixture_odds", return_value=rows), patch.dict(
            os.environ,
            {
                "BETBOT_FOOTBALL_BOOKMAKER_ALLOWLIST": "superbet,sts",
                "BETBOT_FOOTBALL_CONSENSUS_BOOKMAKER_ALLOWLIST": "*",
                "BETBOT_V13_FOOTBALL_MIN_BOOKMAKERS": "2",
            },
            clear=False,
        ):
            markets = data_api.get_odds_market_data({"fixture_id": 123})

        self.assertEqual(markets["OVER_1.5"]["bookmaker"], "Superbet")
        self.assertEqual(markets["OVER_1.5"]["best_odds"], 1.80)
        self.assertEqual(markets["OVER_1.5"]["market_bookmaker_count"], 2)
        self.assertEqual(
            markets["OVER_1.5"]["consensus_bookmaker_scope"],
            "ALL_IDENTIFIABLE_PROVIDER_BOOKMAKERS",
        )
        self.assertTrue(
            markets["OVER_1.5"]["publication_separated_from_consensus"]
        )
        self.assertEqual(markets["UNDER_1.5"]["bookmaker"], "Superbet")

    def test_market_without_polish_publication_quote_stays_quarantined(self):
        rows = [
            self._row("Pinnacle", 20, "OVER_1.5", 1.85),
            self._row("Pinnacle", 20, "UNDER_1.5", 2.00),
            self._row("Bet365", 30, "OVER_1.5", 1.82),
            self._row("Bet365", 30, "UNDER_1.5", 2.02),
        ]
        with patch.object(data_api, "_iter_fixture_odds", return_value=rows), patch.dict(
            os.environ,
            {
                "BETBOT_FOOTBALL_BOOKMAKER_ALLOWLIST": "superbet,sts",
                "BETBOT_FOOTBALL_CONSENSUS_BOOKMAKER_ALLOWLIST": "*",
                "BETBOT_V13_FOOTBALL_MIN_BOOKMAKERS": "2",
            },
            clear=False,
        ):
            markets = data_api.get_odds_market_data({"fixture_id": 456})

        self.assertEqual(markets, {})


class MarketAuditV13Tests(unittest.TestCase):
    def test_class_c_shadow_rows_are_visible_but_never_enter_training_denominator(self):
        class_c = {
            "market_schema": "volleyball.market_integrity_consensus.v13",
            "bookmaker_count": 1,
            "probability_dispersion": 0.0,
            "average_overround": 1.05,
            "market_quality_tier": "C_SINGLE_BOOK_SHADOW",
            "shadow_observation_only": True,
            "training_eligible": False,
            "pick_eligible": False,
            "promotion_eligible": False,
        }
        multi_book = {
            "market_schema": "volleyball.market_integrity_consensus.v13",
            "bookmaker_count": 2,
            "probability_dispersion": 0.01,
            "average_overround": 1.05,
        }
        with patch.dict(
            os.environ,
            {"BETBOT_V13_VOLLEYBALL_MIN_TRAINING_OBSERVATIONS": "50"},
            clear=False,
        ):
            result = _evaluate([class_c] * 100 + [multi_book] * 50, "volleyball")
        self.assertEqual(result["class_c_shadow_observations"], 100)
        self.assertEqual(result["class_c_training_admitted"], 0)
        self.assertEqual(result["v13_observations"], 50)
        self.assertEqual(result["admitted_observations"], 50)
        self.assertTrue(result["training_admission_ready"])

    def test_missing_evidence_blocks_training(self):
        with tempfile.TemporaryDirectory() as folder:
            audit = MarketIntegrityAuditV13(folder)
            report = audit.run()
            self.assertFalse(
                report["sports"]["football"]["training_admission_ready"]
            )
            self.assertFalse(sport_training_ready(folder, "football"))

    def test_quality_rows_open_football_gate_only_after_threshold(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(
            os.environ,
            {"BETBOT_V13_FOOTBALL_MIN_TRAINING_OBSERVATIONS": "50"},
            clear=False,
        ):
            root = Path(folder)
            header = [
                "market_integrity_schema", "market_integrity_status",
                "market_consensus_id", "market_bookmaker_count",
                "market_probability_dispersion", "market_average_overround",
                "bookmaker_verified", "bookmaker_scope", "market_scope",
            ]
            lines = [",".join(header)]
            for index in range(50):
                lines.append(",".join([
                    "betbot.market_data_integrity.v13", "PASS", f"c{index}", "2",
                    "0.02", "1.06", "true", "POLAND_ALLOWLIST", "FULL_MATCH",
                ]))
            (root / "auto_all_picks.csv").write_text(
                "\n".join(lines), encoding="utf-8"
            )
            report = MarketIntegrityAuditV13(root).run()
            self.assertTrue(
                report["sports"]["football"]["training_admission_ready"]
            )
            stored = json.loads(
                (root / "quality_retraining" / "market_integrity_v13.json")
                .read_text(encoding="utf-8")
            )
            self.assertFalse(stored["source_history_modified"])


if __name__ == "__main__":
    unittest.main()
