from __future__ import annotations

import tempfile
import unittest
import sys
import types
from pathlib import Path

import app_launcher
from settings_v81 import ConfigurationError, load_settings
try:
    import requests as _requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.Session = object
    sys.modules["requests"] = requests_stub
from tennis_v1.config import load_tennis_settings
from tennis_v1.domain import TennisMatch, TennisOddsQuote
from tennis_v1.model import build_ratings, predict_match, validate_candidates
from tennis_v1.runtime import admitted_match
from tennis_v1.storage import TennisStorage


def match(
    event_id: str = "sr:match:1",
    *,
    status: str = "not_started",
    winner_id: str = "",
    retired: bool = False,
    surface: str = "hard",
) -> TennisMatch:
    return TennisMatch(
        event_id=event_id,
        scheduled_at="2026-07-30T12:00:00+00:00",
        status=status,
        tour="ATP",
        competition_id="sr:competition:1",
        competition_name="ATP Test",
        competition_level="ATP",
        competition_type="singles",
        surface=surface,
        best_of=3,
        player1_id="p1",
        player1_name="Player One",
        player2_id="p2",
        player2_name="Player Two",
        player1_sets=2 if winner_id else None,
        player2_sets=0 if winner_id else None,
        winner_id=winner_id,
        retired=retired,
        raw={},
    )


class TennisSettingsTests(unittest.TestCase):
    def test_disabled_by_default_and_not_launched(self) -> None:
        settings = load_settings({})
        self.assertFalse(settings.tennis_enabled)
        self.assertEqual(settings.tennis_poll_minutes, 240)
        self.assertNotIn("tennis_shadow", app_launcher.build_process_specs(settings))

    def test_activation_requires_two_provider_keys(self) -> None:
        with self.assertRaises(ConfigurationError):
            load_settings({"BETBOT_TENNIS_ENABLED": "1"})

    def test_activation_adds_only_shadow_process(self) -> None:
        settings = load_settings(
            {
                "BETBOT_TENNIS_ENABLED": "1",
                "BETBOT_TENNIS_SHADOW_ONLY": "1",
                "SPORTRADAR_API_KEY": "radar",
                "THE_ODDS_API_KEY": "odds",
            }
        )
        specs = app_launcher.build_process_specs(settings)
        self.assertIn("tennis_shadow", specs)
        self.assertIn("tennis_v1.runtime", " ".join(specs["tennis_shadow"]))

    def test_existing_odds_api_key_name_is_supported(self) -> None:
        settings = load_settings(
            {
                "BETBOT_TENNIS_ENABLED": "1",
                "SPORTRADAR_API_KEY": "radar",
                "ODDS_API_KEY": "existing-odds-key",
            }
        )
        self.assertTrue(settings.tennis_enabled)

    def test_non_shadow_mode_is_rejected(self) -> None:
        with self.assertRaises(ConfigurationError):
            load_settings(
                {
                    "BETBOT_TENNIS_ENABLED": "1",
                    "BETBOT_TENNIS_SHADOW_ONLY": "0",
                    "SPORTRADAR_API_KEY": "radar",
                    "THE_ODDS_API_KEY": "odds",
                }
            )


class TennisDomainAndStorageTests(unittest.TestCase):
    def test_only_top_singles_are_admitted(self) -> None:
        settings = load_tennis_settings(require_keys=False)
        self.assertEqual(admitted_match(match(), settings), (True, "ADMITTED"))
        challenger = match()
        challenger = TennisMatch(
            **{**challenger.__dict__, "competition_name": "ATP Challenger Test"}
        )
        self.assertEqual(
            admitted_match(challenger, settings)[1], "CHALLENGER_DISABLED"
        )

    def test_consensus_requires_two_distinct_bookmakers(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            storage = TennisStorage(root)
            storage.upsert_matches([match()])
            storage.upsert_odds(
                [
                    TennisOddsQuote(
                        "sr:match:1", "book-a", "Player One", 2.0,
                        "2026-07-30T10:00:00+00:00", "odds-1",
                    ),
                    TennisOddsQuote(
                        "sr:match:1", "book-b", "Player One", 2.2,
                        "2026-07-30T10:00:00+00:00", "odds-1",
                    ),
                    TennisOddsQuote(
                        "sr:match:1", "book-a", "Player Two", 1.8,
                        "2026-07-30T10:00:00+00:00", "odds-1",
                    ),
                ]
            )
            consensus = storage.consensus_odds("sr:match:1", 2)
            self.assertTrue(consensus["Player One"]["admitted"])
            self.assertFalse(consensus["Player Two"]["admitted"])

    def test_retirement_voids_open_pick(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            storage = TennisStorage(root)
            upcoming = match()
            storage.upsert_matches([upcoming])
            storage.save_pick(
                upcoming,
                player_id="p1",
                player_name="Player One",
                probability=0.6,
                bookmaker_odds=2.0,
                bookmaker_count=2,
                confidence=0.7,
                model_id="BASELINE",
            )
            storage.upsert_matches(
                [match(status="closed", winner_id="p1", retired=True)]
            )
            result = storage.settle_picks()
            self.assertEqual(result["void"], 1)
            self.assertEqual(storage.closed_picks()[0]["result"], "VOID")

    def test_model_is_independent_of_bookmaker_odds(self) -> None:
        finished = match(status="closed", winner_id="p1")
        ratings = build_ratings([finished])
        prediction = predict_match(match(event_id="future"), ratings)
        self.assertGreater(prediction["player1_probability"], 0.5)
        waiting = validate_candidates(
            [finished],
            minimum_rows=1500,
            minimum_surface_rows=300,
            test_rows=200,
            minimum_folds=4,
            minimum_brier_improvement=0.002,
        )
        self.assertEqual(waiting["status"], "WAITING_MINIMUM_SAMPLE")

    def test_storage_is_confined_to_tennis_directory(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            storage = TennisStorage(Path(root) / "tennis")
            storage.upsert_matches([match()])
            files = [path.relative_to(root).as_posix() for path in Path(root).rglob("*") if path.is_file()]
            self.assertTrue(files)
            self.assertTrue(all(name.startswith("tennis/") for name in files))


if __name__ == "__main__":
    unittest.main()
