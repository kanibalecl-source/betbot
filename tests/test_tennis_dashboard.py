from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tennis_v1.dashboard import load_tennis_dashboard
from tennis_v1.storage import TennisStorage
from tests.test_tennis_v1 import match


class TennisDashboardTests(unittest.TestCase):
    def test_missing_database_does_not_create_files(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            snapshot = load_tennis_dashboard(root)
            self.assertFalse(snapshot["available"])
            self.assertFalse(Path(root, "tennis_shadow.sqlite3").exists())

    def test_snapshot_is_bounded_and_secret_free(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            storage = TennisStorage(root)
            item = match(status="closed", winner_id="p1")
            storage.upsert_matches([
                type(item)(**{**item.__dict__, "raw": {"api_key": "never-leak"}})
            ])
            storage.set_state(
                "last_health",
                json.dumps(
                    {
                        "status": "HEALTHY",
                        "candidate_dataset_rows": 1,
                        "candidate_minimum_rows": 1500,
                        "active_shadow_model_id": "BASELINE",
                        "automatic_shadow_promotion_allowed": True,
                        "validation": {"status": "WAITING_MINIMUM_SAMPLE"},
                    }
                ),
            )
            snapshot = load_tennis_dashboard(root, match_limit=1)
            self.assertTrue(snapshot["available"])
            self.assertEqual(len(snapshot["matches"]), 1)
            self.assertFalse(snapshot["real_execution_allowed"])
            self.assertNotIn("never-leak", json.dumps(snapshot))

    def test_navigation_and_route_include_tennis(self) -> None:
        base = Path(__file__).resolve().parents[1]
        navigation = (base / "executive_dashboard_theme.py").read_text("utf-8")
        dashboard = (base / "dashboard_streamlit.py").read_text("utf-8")
        self.assertIn('"Tenis"', navigation)
        self.assertIn('selected_page == "Tenis"', dashboard)
        self.assertIn("render_tennis()", dashboard)


if __name__ == "__main__":
    unittest.main()
