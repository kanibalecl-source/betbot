from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from basketball_v1.dashboard import load_basketball_dashboard
from basketball_v1.domain import BasketballGame, BasketballOddsQuote
from basketball_v1.storage import BasketballStorage


class BasketballDashboardTests(unittest.TestCase):
    def test_missing_database_returns_safe_waiting_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            snapshot = load_basketball_dashboard(root)
            self.assertFalse(snapshot["available"])
            self.assertEqual(snapshot["status"], "WAITING_FOR_DATABASE")
            self.assertFalse(snapshot["real_execution_allowed"])
            self.assertFalse(Path(root, "basketball_shadow.sqlite3").exists())

    def test_snapshot_is_bounded_read_only_and_secret_free(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            db_path = Path(root) / "basketball_shadow.sqlite3"
            storage = BasketballStorage(db_path)
            storage.initialize()
            game = BasketballGame(
                game_id="basket-1",
                scheduled_at="2026-07-31T18:00:00+00:00",
                status="FT",
                league_id="league-1",
                league_name="Liga Testowa",
                country="Polska",
                season="2026",
                home_team_id="home-1",
                home_team="Drużyna A",
                away_team_id="away-1",
                away_team="Drużyna B",
                home_score=88,
                away_score=81,
                overtime=False,
                raw={"api_key": "must-never-leak"},
            )
            storage.upsert_games([game])
            storage.save_odds([
                BasketballOddsQuote(
                    game_id="basket-1",
                    bookmaker_id="book-1",
                    bookmaker="Buk Testowy",
                    market="Moneyline",
                    outcome="Home",
                    line=None,
                    odds=1.80,
                    observed_at="2026-07-31T16:00:00+00:00",
                )
            ])
            storage.settle_finished_games()
            storage.set_state(
                "last_health",
                json.dumps({
                    "status": "HEALTHY",
                    "collection_autonomous": True,
                    "settlement_autonomous": True,
                    "database_integrity": True,
                    "training_admission_allowed": False,
                    "model_candidate_creation_allowed": False,
                    "automatic_model_promotion_allowed": False,
                    "real_execution_allowed": False,
                }),
            )

            before = storage.coverage_summary()
            snapshot = load_basketball_dashboard(root, game_limit=1, odds_limit=1)
            after = storage.coverage_summary()

            self.assertTrue(snapshot["available"])
            self.assertEqual(snapshot["status"], "HEALTHY")
            self.assertEqual(len(snapshot["games"]), 1)
            self.assertEqual(snapshot["games"][0]["home_score"], 88)
            self.assertEqual(len(snapshot["odds"]), 1)
            self.assertEqual(snapshot["odds"][0]["bookmaker"], "Buk Testowy")
            self.assertFalse(snapshot["training_admission_allowed"])
            self.assertFalse(snapshot["model_candidate_creation_allowed"])
            self.assertFalse(snapshot["automatic_model_promotion_allowed"])
            self.assertFalse(snapshot["real_execution_allowed"])
            self.assertEqual(before, after)
            self.assertNotIn("must-never-leak", json.dumps(snapshot))

    def test_navigation_and_route_include_basketball(self) -> None:
        base = Path(__file__).resolve().parents[1]
        navigation = (base / "executive_dashboard_theme.py").read_text("utf-8")
        dashboard = (base / "dashboard_streamlit.py").read_text("utf-8")
        self.assertIn('"Koszykówka"', navigation)
        self.assertIn('selected_page == "Koszykówka"', dashboard)
        self.assertIn("render_basketball()", dashboard)


if __name__ == "__main__":
    unittest.main()
