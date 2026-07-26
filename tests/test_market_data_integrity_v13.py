from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_data_integrity_v13 import build_market_consensus
from market_integrity_audit_v13 import MarketIntegrityAuditV13, sport_training_ready


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


class MarketAuditV13Tests(unittest.TestCase):
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
