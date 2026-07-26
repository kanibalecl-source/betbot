import os
import unittest
from unittest.mock import patch

from app.data.postgres_repository import validate_pick
from scripts.sync_fastapi_snapshot import build_snapshot


class PickAdmissionTests(unittest.TestCase):
    def valid(self):
        return {
            "sport": "football",
            "pick_id": "p-1",
            "league": "Test league",
            "match_name": "Alpha vs Beta",
            "market": "OVER_1_5",
            "bookmaker_odds": 2.1,
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


if __name__ == "__main__":
    unittest.main()
