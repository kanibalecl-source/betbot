import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import app_launcher_quality
from quality_auto_retraining import ControlledQualityRetrainer


class ControlledQualityRetrainingTests(unittest.TestCase):
    def _history(self, path: Path, rows: int) -> None:
        fields = [
            "timestamp", "match", "market", "probability",
            "home_xg", "away_xg", "odds", "result",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for index in range(rows):
                won = index % 3 != 0
                writer.writerow({
                    "timestamp": f"2026-01-{(index % 28) + 1:02d}T{index % 24:02d}:00:00Z",
                    "match": f"Home {index} vs Away {index}",
                    "market": "OVER_2_5",
                    "probability": 0.66 if won else 0.42,
                    "home_xg": 1.70 if won else 1.05,
                    "away_xg": 1.20 if won else 0.85,
                    "odds": 1.90,
                    "result": "WON" if won else "LOST",
                })

    def _active(self, data: Path, samples: int) -> Path:
        path = data / "quality_shadow_state.json"
        path.write_text(json.dumps({
            "status": "TRAINED_TIME_SAFE",
            "samples": samples,
            "stacking_weights": {"current": 0.45, "dixon_coles": 0.35, "market": 0.20},
            "beta_calibration": {"a": 1.0, "b": 1.0, "c": 0.0},
        }), encoding="utf-8")
        return path

    def test_waits_for_minimum_new_rows_without_touching_active(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            self._history(data / "results_history.csv", 80)
            active = self._active(data, 80)
            before = active.read_bytes()
            result = ControlledQualityRetrainer(data, min_new_rows=20, min_hours=1).run()
            self.assertEqual(result["status"], "WAITING_FOR_NEW_SETTLED_ROWS")
            self.assertEqual(active.read_bytes(), before)
            self.assertFalse((data / "quality_retraining" / "quality_shadow_state.candidate.latest.json").exists())

    def test_creates_versioned_candidate_but_never_promotes_it(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            self._history(data / "results_history.csv", 90)
            active = self._active(data, 40)
            before = active.read_bytes()
            result = ControlledQualityRetrainer(
                data,
                min_new_rows=20,
                min_hours=1,
                min_brier_improvement=0.0,
                min_log_loss_improvement=0.0,
            ).run()
            self.assertEqual(result["status"], "CANDIDATE_CREATED")
            self.assertFalse(result["active_model_modified"])
            self.assertEqual(active.read_bytes(), before)
            candidate = Path(result["candidate"])
            self.assertTrue(candidate.exists())
            document = json.loads(candidate.read_text(encoding="utf-8"))
            self.assertFalse(document["validation"]["automatic_promotion"])
            self.assertTrue(document["active_model_was_not_modified"])

    def test_force_still_cannot_replace_active_state(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            self._history(data / "results_history.csv", 60)
            active = self._active(data, 60)
            before = active.read_bytes()
            result = ControlledQualityRetrainer(data, min_new_rows=300, min_hours=24).run(force=True)
            self.assertEqual(result["status"], "CANDIDATE_CREATED")
            self.assertEqual(active.read_bytes(), before)

    def test_quality_launcher_wraps_original_and_stops_child(self):
        process = MagicMock()
        process.pid = 123
        process.poll.return_value = None
        with patch.dict("os.environ", {"BETBOT_QUALITY_RETRAIN_ENABLED": "1"}), patch(
            "app_launcher_quality.subprocess.Popen", return_value=process
        ) as popen, patch("app_launcher_quality.runpy.run_path") as run_path:
            app_launcher_quality.main()
        popen.assert_called_once()
        run_path.assert_called_once()
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=10)


if __name__ == "__main__":
    unittest.main()
