from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

import app_launcher
from server_data_guard import snapshot_hashes
from settings_v81 import ConfigurationError, load_settings
try:
    import requests as _requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.Session = object
    sys.modules["requests"] = requests_stub
from volleyball_v9.api_sports import ApiSportsVolleyballClient
from volleyball_v9.config import load_volleyball_settings
from volleyball_v9.domain import VolleyballGame
from volleyball_v9.model import VolleyballEloModel
from volleyball_v9.settlement import settle_match_winner
from volleyball_v9.storage import VolleyballStorage


def game(*, game_id="1", status="FT", home_sets=3, away_sets=1):
    return VolleyballGame(
        game_id=game_id,
        scheduled_at="2026-07-20T18:00:00+00:00",
        status=status,
        league_id="10",
        league_name="Test League",
        country="Poland",
        season="2026",
        home_team_id="home",
        home_team="Home",
        away_team_id="away",
        away_team="Away",
        home_sets=home_sets,
        away_sets=away_sets,
        raw={"id": game_id, "status": status},
    )


class VolleyballSettingsTests(unittest.TestCase):
    def test_default_does_not_start_volleyball(self):
        settings = load_settings({})
        self.assertFalse(settings.volleyball_enabled)
        self.assertNotIn("volleyball_shadow", app_launcher.build_process_specs(settings))

    def test_enabled_adds_only_shadow_process(self):
        settings = load_settings(
            {
                "BETBOT_VOLLEYBALL_ENABLED": "1",
                "BETBOT_VOLLEYBALL_SHADOW_ONLY": "1",
            }
        )
        specs = app_launcher.build_process_specs(settings)
        self.assertIn("volleyball_shadow", specs)
        self.assertIn("volleyball_v9.runtime", " ".join(specs["volleyball_shadow"]))

    def test_non_shadow_volleyball_is_rejected(self):
        with self.assertRaises(ConfigurationError):
            load_settings(
                {
                    "BETBOT_VOLLEYBALL_ENABLED": "1",
                    "BETBOT_VOLLEYBALL_SHADOW_ONLY": "0",
                }
            )


class VolleyballDomainTests(unittest.TestCase):
    def test_settlement_uses_sets_and_handles_void(self):
        self.assertEqual(settle_match_winner("HOME", game()), "WON")
        self.assertEqual(settle_match_winner("AWAY", game()), "LOST")
        self.assertEqual(
            settle_match_winner("HOME", game(status="CANC", home_sets=None, away_sets=None)),
            "VOID",
        )

    def test_elo_learns_without_bookmaker_odds(self):
        model = VolleyballEloModel(home_advantage=0)
        model.fit([game()])
        prediction = model.predict("home", "away")
        self.assertGreater(prediction.home_probability, 0.5)
        self.assertGreater(prediction.home_rating, prediction.away_rating)


class VolleyballStorageTests(unittest.TestCase):
    def test_storage_is_isolated_and_append_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "volleyball"
            storage = VolleyballStorage(root)
            storage.initialize()
            storage.upsert_games([game()])
            self.assertTrue(storage.db_path.is_relative_to(root))
            with storage.connect() as connection:
                sport = connection.execute("SELECT sport FROM games").fetchone()[0]
                self.assertEqual(sport, "volleyball")
                football_tables = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%football%'"
                ).fetchall()
                self.assertEqual(football_tables, [])

    def test_nested_volleyball_database_is_covered_by_server_guard(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            storage = VolleyballStorage(root / "volleyball")
            storage.initialize()
            snapshot = snapshot_hashes(root)
            self.assertIn("volleyball/volleyball_shadow.sqlite3", snapshot)

    def test_public_runtime_settings_never_contains_api_key(self):
        serialized = json.dumps(load_settings({}).public_snapshot()).lower()
        self.assertNotIn("volleyball_api_sports_key", serialized)
        self.assertNotIn("api_key", serialized)

    def test_coverage_counts_only_inserted_odds(self):
        from volleyball_v9.domain import OddsQuote
        with tempfile.TemporaryDirectory() as temporary:
            storage = VolleyballStorage(Path(temporary) / "volleyball")
            storage.initialize()
            upcoming = game(status="NS", home_sets=None, away_sets=None)
            storage.upsert_games([upcoming])
            quote = OddsQuote(
                game_id=upcoming.game_id,
                bookmaker_id="1",
                bookmaker="Test",
                market="MATCH_WINNER",
                outcome="HOME",
                odds=1.90,
                observed_at="2026-07-23T12:00:00+00:00",
            )
            self.assertEqual(storage.save_odds([quote]), 1)
            self.assertEqual(storage.save_odds([quote]), 0)
            coverage = storage.coverage_summary()
            self.assertEqual(coverage["odds_quotes"], 1)
            self.assertEqual(coverage["games_with_odds"], 1)


class _FakeResponse:
    def __init__(self, status_code, payload, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, *args, **kwargs):
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


class VolleyballProviderTests(unittest.TestCase):
    def test_retry_is_bounded_and_observed(self):
        observed = []
        settings = load_volleyball_settings(require_key=False)
        session = _FakeSession(
            [
                _FakeResponse(500, {}),
                _FakeResponse(
                    200,
                    {"errors": [], "response": [{"id": 1}]},
                    {"x-ratelimit-requests-remaining": "99"},
                ),
            ]
        )
        client = ApiSportsVolleyballClient(
            settings, session=session, observer=observed.append
        )
        rows = client._get("games", {"date": "2026-07-23"})
        self.assertEqual(rows, [{"id": 1}])
        self.assertEqual(session.calls, 2)
        self.assertEqual(len(observed), 2)
        self.assertEqual(observed[0]["status"], "RETRY")
        self.assertEqual(observed[-1]["status"], "SUCCESS")
        self.assertEqual(observed[-1]["remaining"], 99)


if __name__ == "__main__":
    unittest.main()
