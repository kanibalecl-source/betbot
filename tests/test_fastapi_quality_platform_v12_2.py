import os
import unittest
from unittest.mock import patch

import pandas as pd

from app.api.v1.postgres_repository import validate_pick
from scripts.sync_fastapi_snapshot import build_snapshot, football_records


class PickAdmissionTests(unittest.TestCase):
    def valid(self):
        return {
            "sport": "football",
            "pick_id": "p-1",
            "league": "Test league",
            "match_name": "Alpha vs Beta",
            "market": "OVER_1_5",
            "bookmaker_odds": 2.1,
            "bookmaker": "Superbet",
            "bookmaker_scope": "POLAND_ALLOWLIST",
            "bookmaker_verified": True,
            "market_scope": "FULL_MATCH",
            "market_integrity_schema": "betbot.market_data_integrity.v13",
            "market_integrity_status": "PASS",
            "market_consensus_id": "consensus-1",
            "market_bookmaker_count": 2,
            "market_probability_dispersion": 0.02,
            "model_probability": 0.61,
            "confidence": 61,
            "status": "OPEN",
            "result": "PENDING",
            "generated_at": "2026-07-26T12:00:00+00:00",
        }

    def test_valid_pick_is_normalized(self):
        row, reason = validate_pick(self.valid())
        self.assertIsNone(reason)
        self.assertEqual(row["sport"], "football")
        self.assertAlmostEqual(row["fair_odds"], 1 / 0.61)

    def test_invalid_odds_are_quarantined(self):
        value = self.valid()
        value["bookmaker_odds"] = 1
        row, reason = validate_pick(value)
        self.assertIsNone(row)
        self.assertEqual(reason, "invalid_odds")

    def test_unverified_football_odds_are_quarantined(self):
        value = self.valid()
        value["bookmaker_verified"] = False
        row, reason = validate_pick(value)
        self.assertIsNone(row)
        self.assertEqual(reason, "unverified_bookmaker_odds")

    def test_wrong_market_scope_is_quarantined(self):
        value = self.valid()
        value["market_scope"] = "FIRST_HALF"
        row, reason = validate_pick(value)
        self.assertIsNone(row)
        self.assertEqual(reason, "invalid_market_scope")

    def test_invalid_probability_is_quarantined(self):
        value = self.valid()
        value["model_probability"] = 140
        row, reason = validate_pick(value)
        self.assertIsNone(row)
        self.assertEqual(reason, "invalid_probability")

    def test_unknown_sport_is_quarantined(self):
        value = self.valid()
        value["sport"] = "tennis"
        row, reason = validate_pick(value)
        self.assertIsNone(row)
        self.assertEqual(reason, "invalid_sport")

    def test_bad_timestamp_is_quarantined(self):
        value = self.valid()
        value["generated_at"] = "not-a-date"
        row, reason = validate_pick(value)
        self.assertIsNone(row)
        self.assertEqual(reason, "invalid_generated_at")


class SnapshotSafetyTests(unittest.TestCase):
    def test_football_match_phase_is_mapped_to_open_pending(self):
        frame = pd.DataFrame(
            [
                {
                    "home_team": "Alpha",
                    "away_team": "Beta",
                    "market": "OVER_1.5",
                    "odds": 2.10,
                    "confidence": 61,
                    "status": "1H",
                }
            ]
        )
        with patch("scripts.sync_fastapi_snapshot.pd.read_csv", return_value=frame):
            row = football_records(limit=10)[0]
        self.assertEqual(row["status"], "OPEN")
        self.assertEqual(row["result"], "PENDING")
        self.assertEqual(row["source_match_status"], "1H")

    def test_football_terminal_result_is_mapped_to_closed(self):
        frame = pd.DataFrame(
            [
                {
                    "home_team": "Alpha",
                    "away_team": "Beta",
                    "market": "OVER_1.5",
                    "odds": 2.10,
                    "confidence": 61,
                    "status": "FT",
                    "result": "WON",
                }
            ]
        )
        with patch("scripts.sync_fastapi_snapshot.pd.read_csv", return_value=frame):
            row = football_records(limit=10)[0]
        self.assertEqual(row["status"], "CLOSED")
        self.assertEqual(row["result"], "WON")
        self.assertEqual(row["source_match_status"], "FT")

    def test_snapshot_builder_is_read_only_and_secret_free(self):
        with patch(
            "scripts.sync_fastapi_snapshot.football_records", return_value=[]
        ), patch(
            "scripts.sync_fastapi_snapshot.shadow_records",
            side_effect=[([], {}), ([], {})],
        ):
            result = build_snapshot()
        self.assertEqual(result["source"], "betbot-main-volume-readonly")
        self.assertEqual(result["records"], [])
        self.assertEqual(len(result["statuses"]), 12)
        serialized = str(result).upper()
        self.assertNotIn("API_KEY", serialized)
        self.assertNotIn("PASSWORD", serialized)

    def test_main_sync_process_is_disabled_by_default(self):
        from app_launcher import build_process_specs
        with patch.dict(os.environ, {"BETBOT_FASTAPI_SYNC_ENABLED": "0"}, clear=False):
            self.assertNotIn("fastapi_snapshot_sync", build_process_specs())

    def test_main_sync_process_uses_module_execution(self):
        from app_launcher import build_process_specs
        with patch.dict(os.environ, {"BETBOT_FASTAPI_SYNC_ENABLED": "1"}, clear=False):
            command = build_process_specs()["fastapi_snapshot_sync"]
        self.assertEqual(command[1:], ["-m", "scripts.sync_fastapi_snapshot"])


if __name__ == "__main__":
    unittest.main()
