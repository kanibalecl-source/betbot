from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import app_launcher
from server_data_guard import snapshot_hashes
from settings_v81 import ConfigurationError, load_settings
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


if __name__ == "__main__":
    unittest.main()
