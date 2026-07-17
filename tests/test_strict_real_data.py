from __future__ import annotations

import tempfile
import unittest
import importlib
import sys
import sqlite3
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import pandas as pd


class StrictRealDataTests(unittest.TestCase):
    def test_own_odds_never_use_bookmaker_probability(self):
        import bot

        first = bot.stage_probability({}, "OVER_2.5", 0.61, 0.20, 5.0, 1.4, 1.1, None, None, None, 0.1, 0.9)
        second = bot.stage_probability({}, "OVER_2.5", 0.61, 0.80, 1.25, 1.4, 1.1, None, None, None, 0.9, 0.1)
        self.assertEqual(first["final_probability"], 0.61)
        self.assertEqual(second["final_probability"], 0.61)
        self.assertAlmostEqual(first["fair_odds_final"], 1 / 0.61)
        self.assertFalse(first["bookmaker_used_in_own_odds"])
        self.assertFalse(first["calibration_applied"])

    def test_missing_probability_is_rejected_not_changed_to_fifty_percent(self):
        import bot

        self.assertIsNone(bot.strict_probability(None))
        self.assertIsNone(bot.strict_probability("nan"))
        self.assertIsNone(bot.stage_probability({}, "BTTS_YES", None, 0.5, 2.0, 1, 1, None, None, None, 1, 0))

    def test_margin_uses_complete_prices_from_the_same_bookmaker(self):
        import bot

        odds = {
            "BTTS_YES": {"by_bookmaker": {"A": 1.90, "B": 1.80}},
            "BTTS_NO": {"by_bookmaker": {"A": 1.90, "C": 1.70}},
        }
        self.assertAlmostEqual(bot.calculate_market_margin(odds, "BTTS_YES"), 2 / 1.9)
        odds["BTTS_NO"]["by_bookmaker"].pop("A")
        self.assertIsNone(bot.calculate_market_margin(odds, "BTTS_YES"))

    def test_goal_model_has_no_fixed_dixon_coles_or_probability_clamp(self):
        import model_goals

        self.assertEqual(model_goals.DIXON_COLES_RHO, 0.0)
        model = model_goals.build_model(0.0, 0.0)
        self.assertGreater(model["DRAW"], 0.99)
        self.assertLess(model["HOME_WIN"], 0.01)

    def test_team_strength_requires_five_finished_matches(self):
        with patch.dict(sys.modules, {"requests": SimpleNamespace(get=lambda *args, **kwargs: None)}):
            import team_stats
            importlib.reload(team_stats)

        def match(status="FT"):
            return {
                "fixture": {"status": {"short": status}},
                "teams": {"home": {"id": 1}, "away": {"id": 2}},
                "goals": {"home": 2, "away": 1},
            }

        with patch.object(team_stats, "get_last_matches", return_value=[match()] * 4 + [match("NS")]):
            self.assertIsNone(team_stats.calculate_team_strength(1, 39))
        with patch.object(team_stats, "get_last_matches", return_value=[match()] * 5):
            attack, defense, games = team_stats.calculate_team_strength(1, 39)
            self.assertEqual((attack, defense, games), (2.0, 1.0, 5))

    def test_legacy_migration_merges_and_never_downgrades_closed_result(self):
        from legacy_data_migration import migrate_legacy_data

        def make_db(data_dir: Path, rows: list[tuple[str, str, str]]) -> None:
            data_dir.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(data_dir / "kanibal_persistent.sqlite3")
            conn.executescript("""
                CREATE TABLE picks_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pick_key TEXT UNIQUE, status TEXT, result TEXT, profit REAL,
                    updated_at TEXT, settled_at TEXT
                );
                CREATE TABLE gpt_analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, analysis_key TEXT UNIQUE
                );
                CREATE TABLE learning_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT, event_type TEXT, payload_json TEXT
                );
            """)
            conn.executemany(
                "INSERT INTO picks_history(pick_key,status,result,profit,updated_at,settled_at) VALUES(?,?,?,?,?,?)",
                [(key, status, result, 1.0 if result == "WIN" else 0.0, "now", "now" if status == "CLOSED" else None) for key, status, result in rows],
            )
            conn.commit()
            conn.close()

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, old_a, old_b = root / "target", root / "old_a", root / "old_b"
            make_db(old_a, [("A", "OPEN", "PENDING")])
            make_db(old_b, [("A", "CLOSED", "WIN"), ("B", "OPEN", "PENDING")])
            (old_a / "ai_learning").mkdir()
            (old_b / "ai_learning").mkdir()
            pd.DataFrame([{"ai_id": "AI-1", "result": "PENDING"}]).to_csv(old_a / "ai_learning" / "ai_feature_store.csv", index=False)
            pd.DataFrame([{"ai_id": "AI-1", "result": "PENDING"}, {"ai_id": "AI-2", "result": "PENDING"}]).to_csv(old_b / "ai_learning" / "ai_feature_store.csv", index=False)

            summary = migrate_legacy_data(target, [old_a, old_b])
            self.assertEqual(summary["sources"], 2)
            conn = sqlite3.connect(target / "kanibal_persistent.sqlite3")
            rows = conn.execute("SELECT pick_key,status,result FROM picks_history ORDER BY pick_key").fetchall()
            conn.close()
            self.assertEqual(rows, [("A", "CLOSED", "WIN"), ("B", "OPEN", "PENDING")])
            merged = pd.read_csv(target / "ai_learning" / "ai_feature_store.csv")
            self.assertEqual(set(merged["ai_id"]), {"AI-1", "AI-2"})

    def test_hidden_prompt_v2_uses_clicked_match_and_new_analysis_scope(self):
        from gpt_prompts import build_hidden_match_analysis_prompt

        prompt = build_hidden_match_analysis_prompt({
            "match": "Wisla vs Legia",
            "league": "Ekstraklasa",
            "time": "2026-07-18 20:00 Europe/Warsaw",
            "bet": "OVER_2.5",
            "odds": 1.91,
            "source_row": {"stadium": "Stadion Testowy"},
        })
        self.assertIn("Mecz: Wisla vs Legia", prompt)
        self.assertIn("ostatnie 10 spotkań", prompt)
        self.assertIn("prawdopodobienstwa", prompt)
        self.assertIn("Stadion Testowy", prompt)
        self.assertNotIn("[DRUŻYNA A]", prompt)

    def test_team_stats_do_not_invent_strength(self):
        with patch.dict(sys.modules, {"requests": SimpleNamespace(get=lambda *args, **kwargs: None)}):
            import team_stats
            importlib.reload(team_stats)

            with patch.object(team_stats, "get_last_matches", return_value=[]):
                self.assertIsNone(team_stats.calculate_team_strength(1, 39))
                self.assertEqual(
                    team_stats.get_match_xg({"home_id": 1, "away_id": 2, "league_id": 39}),
                    (None, None),
                )

    def test_learning_uses_only_closed_results(self):
        import ai_self_learning_runtime as ai

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old_results = ai.RESULTS_FILE
            try:
                ai.RESULTS_FILE = root / "results_history.csv"
                pd.DataFrame([
                    {"pick_key": "closed", "status": "CLOSED", "result": "WIN", "league": "L", "market": "OVER_2.5"},
                    {"pick_key": "open", "status": "OPEN", "result": "PENDING", "league": "L", "market": "OVER_2.5"},
                ]).to_csv(ai.RESULTS_FILE, index=False)
                result = ai.combine_results()
                self.assertEqual(len(result), 1)
                self.assertEqual(result.iloc[0]["pick_key"], "closed")
            finally:
                ai.RESULTS_FILE = old_results

    def test_ai_ranks_existing_verified_pick_without_changing_market_or_odds(self):
        import ai_self_learning_runtime as ai

        with tempfile.TemporaryDirectory() as temp:
            old_data_dir = ai.DATA_DIR
            try:
                ai.DATA_DIR = Path(temp)
                ai.configure_ai_mode("main")
                pd.DataFrame([{
                    "pick_id": "P-1", "fixture_id": "123", "league": "Test League",
                    "match": "A vs B", "market": "OVER_2.5", "odds": 1.91,
                    "confidence": 70.0, "edge": 0.05, "ev": 0.04, "stake": 12.5,
                }]).to_csv(ai.PREMATCH_FILE, index=False)
                with patch.object(ai, "append_event"), patch.object(ai, "append_records"):
                    picks = ai.build_ai_picks(limit=5, mode="main")
                self.assertEqual(len(picks), 1)
                row = picks.iloc[0]
                self.assertEqual(row["market"], "OVER_2.5")
                self.assertEqual(float(row["odds"]), 1.91)
                self.assertEqual(float(row["edge"]), 0.05)
                self.assertEqual(float(row["stake"]), 12.5)
                self.assertEqual(row["fixture_id"], "123")
                self.assertEqual(row["data_provenance"], "VERIFIED_PREMATCH_PICK+SETTLED_HISTORY")
            finally:
                ai.DATA_DIR = old_data_dir
                ai.configure_ai_mode("main")

    def test_empty_ai_cycle_does_not_overwrite_previous_output(self):
        import ai_self_learning_runtime as ai

        with tempfile.TemporaryDirectory() as temp:
            old_data_dir = ai.DATA_DIR
            try:
                ai.DATA_DIR = Path(temp)
                ai.configure_ai_mode("main")
                ai.AI_PICKS_FILE.write_text("sentinel\n", encoding="utf-8")
                before = ai.AI_PICKS_FILE.read_bytes()
                with patch.object(ai, "append_event"), patch.object(ai, "append_records"):
                    ai.run_self_learning_cycle(mode="main")
                self.assertEqual(ai.AI_PICKS_FILE.read_bytes(), before)
            finally:
                ai.DATA_DIR = old_data_dir
                ai.configure_ai_mode("main")

    def test_ml_rejects_open_or_new_rows(self):
        from ml_training_pipeline import MLTrainingPipeline

        with tempfile.TemporaryDirectory() as temp:
            ml = MLTrainingPipeline(temp)
            self.assertFalse(ml._has_target({"status": "NEW", "probability": 0.6, "odds": 1.9}))
            report = ml.train([{"status": "OPEN", "probability": 0.6, "odds": 1.9}])
            self.assertEqual(report["status"], "NO_SETTLED_DATA")

    def test_all_active_databases_use_shared_data_directory(self):
        import agi_storage
        import database
        import storage_paths

        self.assertEqual(database.DB_FILE.parent.resolve(), storage_paths.DATA_DIR.resolve())
        self.assertEqual(agi_storage.DB_FILE.parent.resolve(), storage_paths.DATA_DIR.resolve())

    def test_server_start_fails_without_persistent_volume(self):
        import storage_paths

        with patch.dict("os.environ", {"RAILWAY_ENVIRONMENT": "production"}, clear=False):
            with patch.object(storage_paths, "DATA_DIR", storage_paths.BASE_DIR / "data"):
                with self.assertRaises(RuntimeError):
                    storage_paths.require_persistent_storage_on_server()

    def test_settlement_is_audited_and_closed_record_is_immutable(self):
        import agi_storage

        requests_stub = SimpleNamespace(get=lambda *args, **kwargs: None)
        with patch.dict(sys.modules, {"requests": requests_stub}):
            import result_updater_unified as updater
            importlib.reload(updater)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = (agi_storage.DATA_DIR, agi_storage.DB_FILE, agi_storage.HISTORY_EXPORT)
            old_key = updater.API_KEY
            try:
                agi_storage.DATA_DIR = root
                agi_storage.DB_FILE = root / "memory.sqlite3"
                agi_storage.HISTORY_EXPORT = root / "results_history.csv"
                updater.API_KEY = "test-key"
                agi_storage.init_storage()
                c = agi_storage.conn()
                c.execute("""
                    INSERT INTO picks_history (
                        pick_key, created_at, updated_at, source, fixture_id, league,
                        match_name, market, bet_name, odds, confidence, edge, ev,
                        probability, stake, status, result, profit, roi, raw_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    "P-SETTLE", agi_storage.now_iso(), agi_storage.now_iso(), "test", "99", "L",
                    "A vs B", "OVER_2.5", "Over 2.5", 2.0, 70, 0.05, 0.04,
                    0.6, 10.0, "OPEN", "PENDING", 0, 0, "{}",
                ))
                c.commit()
                c.close()
                with patch.object(updater, "fetch_result", return_value={
                    "home_goals": 2, "away_goals": 1, "status": "FT",
                    "fixture_id": "99", "source": "API_FOOTBALL",
                }) as fetch:
                    first = updater.settle_stored_picks()
                    second = updater.settle_stored_picks()
                    self.assertEqual(first["settled"], 1)
                    self.assertEqual(second["settled"], 0)
                    self.assertEqual(fetch.call_count, 1)
                c = agi_storage.conn()
                row = c.execute("SELECT * FROM picks_history WHERE pick_key='P-SETTLE'").fetchone()
                c.close()
                self.assertEqual(row["status"], "CLOSED")
                self.assertEqual(row["result"], "WIN")
                self.assertEqual(row["result_score"], "2:1")
                self.assertEqual(row["settlement_source"], "API_FOOTBALL")
            finally:
                agi_storage.DATA_DIR, agi_storage.DB_FILE, agi_storage.HISTORY_EXPORT = old
                updater.API_KEY = old_key

    def test_manual_settlement_records_real_source(self):
        import database

        requests_stub = SimpleNamespace(get=lambda *args, **kwargs: None)
        with patch.dict(sys.modules, {"requests": requests_stub}):
            import api_results
            import manual_betting
            importlib.reload(api_results)
            importlib.reload(manual_betting)

        with tempfile.TemporaryDirectory() as temp:
            old_db = database.DB_FILE
            old_dir = database.DATA_DIR
            try:
                database.DATA_DIR = Path(temp)
                database.DB_FILE = Path(temp) / "manual.sqlite3"
                manual_betting.init_manual_db()
                c = database.get_conn()
                c.execute("""
                    INSERT INTO manual_bets (
                        created_at, updated_at, fixture_id, match_name, manual_market,
                        odds, stake, status, result
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                """, (manual_betting.now_text(), manual_betting.now_text(), "7", "A vs B", "BTTS_YES", 1.9, 10, "OPEN", "PENDING"))
                c.commit()
                c.close()
                with patch.object(manual_betting, "get_match_result_by_id", return_value={
                    "finished": True, "home_goals": 1, "away_goals": 1,
                }):
                    self.assertEqual(manual_betting.settle_manual_open_bets(), 1)
                c = database.get_conn()
                row = c.execute("SELECT * FROM manual_bets").fetchone()
                c.close()
                self.assertEqual(row["result"], "WIN")
                self.assertEqual(row["settlement_source"], "API_FOOTBALL")
                self.assertTrue(row["settled_at"])
            finally:
                database.DATA_DIR = old_dir
                database.DB_FILE = old_db


if __name__ == "__main__":
    unittest.main()
