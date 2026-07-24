from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from volleyball_v9.dashboard import load_volleyball_dashboard
from volleyball_v9.domain import VolleyballGame
from volleyball_v9.storage import VolleyballStorage


class VolleyballDashboardTests(unittest.TestCase):
    def test_missing_database_returns_safe_waiting_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            snapshot = load_volleyball_dashboard(root)
            self.assertFalse(snapshot["available"])
            self.assertEqual(snapshot["status"], "WAITING_FOR_DATABASE")
            self.assertFalse(snapshot["real_execution_allowed"])
            self.assertFalse(snapshot["football_data_modified"])
            self.assertFalse(Path(root, "volleyball_shadow.sqlite3").exists())

    def test_snapshot_is_read_only_bounded_and_secret_free(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            storage = VolleyballStorage(root)
            storage.initialize()
            storage.upsert_games([
                VolleyballGame(
                    game_id="volley-1",
                    scheduled_at="2026-07-23T18:00:00+00:00",
                    status="FT",
                    league_id="league-1",
                    league_name="Liga Testowa",
                    country="Polska",
                    season="2026",
                    home_team_id="home-1",
                    home_team="Drużyna A",
                    away_team_id="away-1",
                    away_team="Drużyna B",
                    home_sets=3,
                    away_sets=1,
                    raw={"api_key": "must-never-leak"},
                )
            ])
            storage.set_state(
                "last_health",
                json.dumps({
                    "status": "HEALTHY",
                    "candidate_dataset_rows": 4,
                    "candidate_minimum_rows": 100,
                    "active_shadow_model_id": "BASELINE",
                    "autonomous_governor_status":
                        "WAITING_REPRODUCIBLE_CANDIDATE",
                    "autonomous_governor_enabled": True,
                    "shadow_only": True,
                    "real_execution_allowed": False,
                    "football_data_modified": False,
                }),
            )
            before = storage.coverage_summary()
            snapshot = load_volleyball_dashboard(root, game_limit=1)
            after = storage.coverage_summary()

            self.assertTrue(snapshot["available"])
            self.assertEqual(snapshot["status"], "HEALTHY")
            self.assertEqual(snapshot["candidate_rows"], 4)
            self.assertEqual(snapshot["candidate_minimum_rows"], 100)
            self.assertEqual(snapshot["active_model_id"], "BASELINE")
            self.assertTrue(snapshot["governor_enabled"])
            self.assertTrue(snapshot["shadow_only"])
            self.assertFalse(snapshot["real_execution_allowed"])
            self.assertFalse(snapshot["football_data_modified"])
            self.assertEqual(len(snapshot["games"]), 1)
            self.assertEqual(snapshot["games"][0]["home_sets"], 3)
            self.assertEqual(before, after)
            self.assertNotIn("must-never-leak", json.dumps(snapshot))

    def test_web_navigation_and_route_include_volleyball(self) -> None:
        base = Path(__file__).resolve().parents[1]
        navigation = (base / "executive_dashboard_theme.py").read_text(
            encoding="utf-8"
        )
        dashboard = (base / "dashboard_streamlit.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"Siatkówka"', navigation)
        self.assertIn('selected_page == "Siatkówka"', dashboard)
        self.assertIn("render_volleyball()", dashboard)


if __name__ == "__main__":
    unittest.main()

