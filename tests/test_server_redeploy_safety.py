from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ServerRedeploySafetyTests(unittest.TestCase):
    def test_standard_railway_data_mount_is_accepted_without_extra_path_variable(self):
        import storage_paths

        with patch.dict("os.environ", {
            "RAILWAY_ENVIRONMENT": "production",
            "PERSISTENT_DATA_DIR": "",
            "KANIBAL_DATA_DIR": "",
            "RAILWAY_VOLUME_MOUNT_PATH": "",
        }, clear=False), patch.object(storage_paths, "DATA_DIR", Path("/data")):
            self.assertTrue(storage_paths.persistent_storage_configured())
            storage_paths.require_persistent_storage_on_server()

    def test_two_redeploy_backups_do_not_modify_volume_sources(self):
        from server_data_guard import prepare_server_data_backup

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            code = root / "code"
            volume = root / "volume"
            code.mkdir()
            volume.mkdir()
            db = volume / "kanibal_persistent.sqlite3"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE picks_history(pick_key TEXT,status TEXT,result TEXT)")
            conn.execute("INSERT INTO picks_history VALUES('HISTORY-SENTINEL','CLOSED','WIN')")
            conn.commit()
            conn.close()
            results = volume / "results_history.csv"
            results.write_text("pick_key,status,result\nHISTORY-SENTINEL,CLOSED,WIN\n", encoding="utf-8")
            model = volume / "ai_learning" / "ai_model_state.json"
            model.parent.mkdir()
            model.write_text('{"trained": 77}', encoding="utf-8")
            before = {path: sha256(path) for path in (db, results, model)}

            first = prepare_server_data_backup(volume, code, "deploy-one", force_server=True)
            repeated = prepare_server_data_backup(volume, code, "deploy-one", force_server=True)
            second = prepare_server_data_backup(volume, code, "deploy-two", force_server=True)

            self.assertEqual(first["status"], "BACKUP_CREATED")
            self.assertEqual(repeated["status"], "ALREADY_BACKED_UP")
            self.assertEqual(second["status"], "BACKUP_CREATED")
            self.assertEqual(before, {path: sha256(path) for path in (db, results, model)})
            conn = sqlite3.connect(db)
            row = conn.execute("SELECT * FROM picks_history").fetchone()
            conn.close()
            self.assertEqual(row, ("HISTORY-SENTINEL", "CLOSED", "WIN"))
            for deployment in ("deploy-one", "deploy-two"):
                manifest = volume / "server_backups" / "deployments" / deployment / "manifest.json"
                self.assertTrue(manifest.exists())
                self.assertGreaterEqual(len(json.loads(manifest.read_text(encoding="utf-8"))["files"]), 3)

    def test_server_guard_rejects_data_bundled_inside_deploy(self):
        from server_data_guard import prepare_server_data_backup

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            code, volume = root / "code", root / "volume"
            (code / "data").mkdir(parents=True)
            volume.mkdir()
            (code / "data" / "results_history.csv").write_text("must-not-ship", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                prepare_server_data_backup(volume, code, "unsafe", force_server=True)

    def test_sync_never_rewrites_closed_historical_pick(self):
        import agi_storage

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = (agi_storage.DATA_DIR, agi_storage.DB_FILE, agi_storage.HISTORY_EXPORT, agi_storage.PICK_FILES)
            try:
                agi_storage.DATA_DIR = root
                agi_storage.DB_FILE = root / "history.sqlite3"
                agi_storage.HISTORY_EXPORT = root / "results_history.csv"
                source = root / "auto_all_picks.csv"
                row = {"fixture_id": "77", "match": "A vs B", "market": "OVER_2.5", "odds": 1.80, "stake": 10}
                with source.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=row)
                    writer.writeheader()
                    writer.writerow(row)
                agi_storage.PICK_FILES = [source]
                agi_storage.init_storage()
                normalized = agi_storage.normalize_pick(row, source.name)
                conn = agi_storage.conn()
                conn.execute(
                    "INSERT INTO picks_history(pick_key,status,result,odds,raw_json) VALUES(?,?,?,?,?)",
                    (normalized["pick_key"], "CLOSED", "WIN", 2.25, "historical-sentinel"),
                )
                conn.commit()
                conn.close()
                agi_storage.sync_picks_from_csv()
                conn = agi_storage.conn()
                saved = conn.execute("SELECT status,result,odds,raw_json FROM picks_history").fetchone()
                conn.close()
                self.assertEqual(tuple(saved), ("CLOSED", "WIN", 2.25, "historical-sentinel"))
            finally:
                agi_storage.DATA_DIR, agi_storage.DB_FILE, agi_storage.HISTORY_EXPORT, agi_storage.PICK_FILES = old

    def test_history_export_is_not_limited_to_five_thousand_rows(self):
        import agi_storage

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = (agi_storage.DATA_DIR, agi_storage.DB_FILE, agi_storage.HISTORY_EXPORT)
            try:
                agi_storage.DATA_DIR = root
                agi_storage.DB_FILE = root / "history.sqlite3"
                agi_storage.HISTORY_EXPORT = root / "results_history.csv"
                agi_storage.init_storage()
                conn = agi_storage.conn()
                conn.executemany(
                    "INSERT INTO picks_history(pick_key,created_at,status,result) VALUES(?,?,?,?)",
                    [(f"P-{idx}", f"2026-01-01T00:{idx % 60:02d}:00Z", "CLOSED", "WIN") for idx in range(5001)],
                )
                conn.commit()
                conn.close()
                agi_storage.export_history_csv()
                with agi_storage.HISTORY_EXPORT.open("r", encoding="utf-8") as handle:
                    self.assertEqual(sum(1 for _ in csv.DictReader(handle)), 5001)
            finally:
                agi_storage.DATA_DIR, agi_storage.DB_FILE, agi_storage.HISTORY_EXPORT = old


if __name__ == "__main__":
    unittest.main()
