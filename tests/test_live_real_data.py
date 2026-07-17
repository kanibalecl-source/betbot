import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import live_pipeline_runtime as live


class _Response:
    def __init__(self, payload, status_error=None):
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        return self.payload


def _verified_fixture():
    return {
        "fixture": {
            "id": 123,
            "timestamp": 1784300000,
            "status": {"short": "2H", "elapsed": 67},
        },
        "league": {"name": "Real League"},
        "teams": {"home": {"name": "Home"}, "away": {"name": "Away"}},
        "goals": {"home": 1, "away": 0},
    }


class LiveRealDataTests(unittest.TestCase):
    def test_fixture_only_row_does_not_invent_pick_confidence_or_risk(self):
        responses = [
            _Response({"errors": {}, "response": [_verified_fixture()]}),
            _Response({"errors": {}, "response": []}),
            _Response({"errors": {}, "response": []}),
        ]
        with patch.object(live, "API_FOOTBALL_KEY", "test"), patch.object(
            live.requests, "get", side_effect=responses
        ):
            rows = live.fetch_live_matches()

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["score"], "1:0")
        self.assertEqual(row["minute"], 67)
        self.assertEqual(row["signal"], "")
        self.assertFalse(row["signal_verified"])
        self.assertEqual(row["confidence"], "")
        self.assertEqual(row["risk"], "")
        self.assertEqual(row["data_status"], "VERIFIED_FIXTURE_ONLY")

    def test_real_odd_keeps_market_and_bookmaker_source(self):
        stats = [
            {"statistics": [{"type": "Shots on Goal", "value": 4}]},
            {"statistics": [{"type": "Shots on Goal", "value": 2}]},
        ]
        odds = [{
            "bookmakers": [{
                "name": "Verified Book",
                "bets": [{"name": "Goals Over/Under", "values": [{"value": "Over 2.5", "odd": "2.05"}]}],
            }],
        }]
        responses = [
            _Response({"errors": {}, "response": [_verified_fixture()]}),
            _Response({"errors": {}, "response": stats}),
            _Response({"errors": {}, "response": odds}),
        ]
        with patch.object(live, "API_FOOTBALL_KEY", "test"), patch.object(
            live.requests, "get", side_effect=responses
        ):
            rows = live.fetch_live_matches()

        row = rows[0]
        self.assertTrue(row["odds_verified"])
        self.assertEqual(row["odds"], 2.05)
        self.assertEqual(row["odds_market"], "Goals Over/Under: Over 2.5")
        self.assertEqual(row["odds_bookmaker"], "Verified Book")
        self.assertFalse(row["signal_verified"])

    def test_incomplete_or_non_live_fixture_is_rejected(self):
        incomplete = _verified_fixture()
        incomplete["goals"] = {"home": None, "away": 0}
        prematch = _verified_fixture()
        prematch["fixture"] = {"id": 456, "status": {"short": "NS", "elapsed": 0}}
        with patch.object(live, "API_FOOTBALL_KEY", "test"), patch.object(
            live.requests,
            "get",
            return_value=_Response({"errors": {}, "response": [incomplete, prematch]}),
        ):
            self.assertEqual(live.fetch_live_matches(), [])

    def test_provider_failure_preserves_last_valid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            live_file = data_dir / "live_matches.csv"
            original = "fixture_id,league\n123,Old valid data\n"
            live_file.write_text(original, encoding="utf-8")
            with patch.object(live, "DATA_DIR", data_dir), patch.object(
                live, "LIVE_FILE", live_file
            ), patch.object(live, "API_FOOTBALL_KEY", "test"), patch.object(
                live.requests,
                "get",
                return_value=_Response({"errors": {"rateLimit": "limit"}, "response": []}),
            ):
                with self.assertRaises(live.LiveDataError):
                    live.run_once()
            self.assertEqual(live_file.read_text(encoding="utf-8"), original)

    def test_successful_zero_live_response_clears_rows_without_fake_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            live_file = data_dir / "live_matches.csv"
            pd.DataFrame([{"fixture_id": 123, "league": "Old"}]).to_csv(live_file, index=False)
            with patch.object(live, "DATA_DIR", data_dir), patch.object(
                live, "LIVE_FILE", live_file
            ), patch.object(live, "API_FOOTBALL_KEY", "test"), patch.object(
                live.requests,
                "get",
                return_value=_Response({"errors": {}, "response": []}),
            ):
                self.assertEqual(live.run_once(), 0)
            saved = pd.read_csv(live_file)
            self.assertTrue(saved.empty)
            self.assertEqual(list(saved.columns), live.LIVE_COLUMNS)


if __name__ == "__main__":
    unittest.main()
