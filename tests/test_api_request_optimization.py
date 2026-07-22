import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api_football_request_control import fetch_fixture_odds


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class ApiRequestOptimizationTests(unittest.TestCase):
    def test_fixture_odds_are_shared_through_cache(self):
        calls = []

        def requester(*args, **kwargs):
            calls.append((args, kwargs))
            return _Response({"errors": [], "response": [{"fixture": {"id": 123}}]})

        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "PERSISTENT_DATA_DIR": directory,
                "API_FOOTBALL_ODDS_CACHE_SECONDS": "240",
                "API_FOOTBALL_ODDS_MIN_INTERVAL_SECONDS": "0",
            },
            clear=False,
        ):
            first = fetch_fixture_odds("123", "https://example.test/odds", {}, requester)
            second = fetch_fixture_odds("123", "https://example.test/odds", {}, requester)

        self.assertEqual(len(calls), 1)
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(first["observed_at"], second["observed_at"])

    def test_rate_limit_response_is_not_cached(self):
        calls = []

        def requester(*args, **kwargs):
            calls.append((args, kwargs))
            if len(calls) == 1:
                return _Response({"errors": {"rateLimit": "Too many requests"}, "response": []})
            return _Response({"errors": [], "response": [{"fixture": {"id": 456}}]})

        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "PERSISTENT_DATA_DIR": directory,
                "API_FOOTBALL_ODDS_CACHE_SECONDS": "240",
                "API_FOOTBALL_ODDS_MIN_INTERVAL_SECONDS": "0",
                "API_FOOTBALL_RATE_LIMIT_COOLDOWN_SECONDS": "0",
            },
            clear=False,
        ):
            first = fetch_fixture_odds("456", "https://example.test/odds", {}, requester)
            second = fetch_fixture_odds("456", "https://example.test/odds", {}, requester)

        self.assertEqual(len(calls), 2)
        self.assertTrue(first["rate_limited"])
        self.assertFalse(second["rate_limited"])
        self.assertFalse(second["cached"])

    def test_runtime_cache_contains_no_history_files(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "PERSISTENT_DATA_DIR": directory,
                "API_FOOTBALL_ODDS_MIN_INTERVAL_SECONDS": "0",
            },
            clear=False,
        ):
            fetch_fixture_odds(
                "789",
                "https://example.test/odds",
                {},
                lambda *args, **kwargs: _Response({"errors": [], "response": []}),
            )
            names = {path.name for path in Path(directory).rglob("*") if path.is_file()}

        self.assertTrue(names <= {"odds_cache.json", "request_state.json"})


if __name__ == "__main__":
    unittest.main()
