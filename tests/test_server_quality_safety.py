import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from build_quality_training_from_history import build
from server_data_guard import prepare_server_data_backup, sha256_file


class ServerQualitySafetyTests(unittest.TestCase):
    def _history(self, path: Path, rows: int = 40) -> None:
        fields = [
            "timestamp", "match", "market", "probability",
            "home_xg", "away_xg", "odds", "result",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for index in range(rows):
                won = index % 2 == 0
                writer.writerow({
                    "timestamp": f"2026-01-{(index % 28) + 1:02d}T12:00:00Z",
                    "match": f"Home {index} vs Away {index}",
                    "market": "OVER_2_5",
                    "probability": 0.62 if won else 0.48,
                    "home_xg": 1.55,
                    "away_xg": 1.10,
                    "odds": 1.95,
                    "result": "WON" if won else "LOST",
                })

    def test_history_extraction_is_read_only_and_atomic(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder) / "volume"
            data.mkdir()
            history = data / "results_history.csv"
            self._history(history)
            before = sha256_file(history)
            output = data / "quality_training.csv"
            result = build(data, output)
            self.assertEqual(result["training_rows"], 40)
            self.assertTrue(result["source_hashes_unchanged"])
            self.assertEqual(before, sha256_file(history))
            self.assertTrue(output.exists())
            self.assertFalse(output.with_suffix(".csv.tmp").exists())
            with self.assertRaises(FileExistsError):
                build(data, output)

    def test_production_raw_json_schema_is_usable(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            history = data / "results_history.csv"
            fields = ["pick_key", "created_at", "odds", "probability", "status", "result", "raw_json"]
            with history.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "pick_key": "server-row-1",
                    "created_at": "2026-07-20T12:00:00Z",
                    "odds": 1.48,
                    "probability": 0.7077,
                    "status": "SETTLED",
                    "result": "WON",
                    "raw_json": json.dumps({
                        "home_xg": 1.05,
                        "away_xg": 1.133,
                        "market": "DOUBLE_12",
                    }),
                })
            result = build(data, data / "quality_training.csv")
            self.assertEqual(result["training_rows"], 1)

    def test_volatile_pick_files_are_not_training_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            self._history(data / "results_history.csv", rows=3)
            self._history(data / "auto_risk_picks.csv", rows=7)
            result = build(data, data / "quality_training.csv")
            self.assertEqual(result["source_files"], 1)
            self.assertEqual(result["training_rows"], 3)

    def test_guard_rejects_bundled_deployment_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            code = root / "code"
            volume = root / "volume"
            (code / "data").mkdir(parents=True)
            volume.mkdir()
            (code / "data" / "history.csv").write_text("x\n1\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                prepare_server_data_backup(
                    volume,
                    base_dir=code,
                    deployment_key="test",
                    force_server=True,
                )

    def test_guard_backup_preserves_source_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            code = root / "code"
            volume = root / "volume"
            code.mkdir()
            volume.mkdir()
            history = volume / "results_history.csv"
            self._history(history, rows=4)
            before = sha256_file(history)
            result = prepare_server_data_backup(
                volume,
                base_dir=code,
                deployment_key="safe_deploy",
                force_server=True,
            )
            self.assertEqual(result["status"], "BACKUP_CREATED")
            self.assertEqual(before, sha256_file(history))
            backup = volume / "server_backups" / "deployments" / "safe_deploy"
            self.assertTrue((backup / "manifest.json").exists())
            self.assertTrue((backup / "results_history.csv").exists())
            repeated = prepare_server_data_backup(
                volume,
                base_dir=code,
                deployment_key="safe_deploy",
                force_server=True,
            )
            self.assertEqual(repeated["status"], "ALREADY_BACKED_UP")

    def test_guard_creates_backup_for_each_deployment(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            code = root / "code"
            volume = root / "volume"
            code.mkdir()
            volume.mkdir()
            history = volume / "results_history.csv"
            self._history(history, rows=4)
            first = prepare_server_data_backup(
                volume,
                base_dir=code,
                deployment_key="first",
                force_server=True,
            )
            self.assertEqual(first["status"], "BACKUP_CREATED")
            before = sha256_file(history)
            second = prepare_server_data_backup(
                volume,
                base_dir=code,
                deployment_key="second",
                force_server=True,
            )
            self.assertEqual(second["status"], "BACKUP_CREATED")
            self.assertEqual(before, sha256_file(history))
            backups = volume / "server_backups" / "deployments"
            self.assertTrue((backups / "first" / "manifest.json").exists())
            self.assertTrue((backups / "second" / "manifest.json").exists())

    def test_guard_prunes_old_backup_only_after_new_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            code = root / "code"
            volume = root / "volume"
            code.mkdir()
            volume.mkdir()
            self._history(volume / "results_history.csv", rows=4)
            with patch.dict(
                "os.environ",
                {
                    "BETBOT_SERVER_BACKUP_REUSE_HOURS": "0",
                    "BETBOT_SERVER_BACKUP_KEEP": "1",
                },
            ):
                first = prepare_server_data_backup(
                    volume,
                    base_dir=code,
                    deployment_key="first",
                    force_server=True,
                )
                second = prepare_server_data_backup(
                    volume,
                    base_dir=code,
                    deployment_key="second",
                    force_server=True,
                )
            self.assertEqual(first["status"], "BACKUP_CREATED")
            self.assertEqual(second["status"], "BACKUP_CREATED")
            self.assertEqual(second["pruned_backups"], ["first"])
            backups = volume / "server_backups" / "deployments"
            self.assertFalse((backups / "first").exists())
            self.assertTrue((backups / "second" / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
