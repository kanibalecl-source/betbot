import math
import os
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


try:
    import requests  # noqa: F401
except ImportError:
    requests_stub = types.ModuleType("requests")
    requests_stub.get = lambda *args, **kwargs: None
    sys.modules["requests"] = requests_stub

import bot
import data_api
import execution_guard
import server_data_guard


class StrictProbabilityTests(unittest.TestCase):
    def test_rejects_missing_non_finite_and_boundaries(self):
        invalid = [None, "", "nan", float("nan"), float("inf"), -0.1, 0, 1, 1.1, object()]
        for value in invalid:
            with self.subTest(value=value):
                self.assertIsNone(bot.strict_probability(value))

    def test_accepts_only_open_unit_interval(self):
        self.assertEqual(bot.strict_probability("0.625"), 0.625)


class OwnOddsIndependenceTests(unittest.TestCase):
    def test_market_probability_never_changes_own_probability(self):
        first = bot.stage_probability({}, "BTTS_YES", 0.61, 0.20, 4.0, 1.2, 1.0, 0, 0, 0, 0.85, 0.15)
        second = bot.stage_probability({}, "BTTS_YES", 0.61, 0.90, 1.2, 1.2, 1.0, 0, 0, 0, 0.10, 0.90)
        self.assertEqual(first["final_probability"], 0.61)
        self.assertEqual(first["final_probability"], second["final_probability"])
        self.assertFalse(first["bookmaker_used_in_own_odds"])
        self.assertFalse(first["calibration_applied"])

    def test_missing_model_probability_fails_closed(self):
        self.assertIsNone(bot.stage_probability({}, "BTTS_YES", None, 0.5, 2.0, 1, 1, 0, 0, 0, 1, 0))


class SameBookmakerMarginTests(unittest.TestCase):
    def setUp(self):
        self.odds = {
            "BTTS_YES": {
                "best_odds": 2.10,
                "bookmaker": "B",
                "by_bookmaker": {"A": 1.90, "B": 2.10},
                "observed_at": "2026-07-22T12:00:00+00:00",
            },
            "BTTS_NO": {
                "best_odds": 2.05,
                "bookmaker": "A",
                "by_bookmaker": {"A": 2.05, "B": 1.80},
                "observed_at": "2026-07-22T12:00:00+00:00",
            },
        }

    def test_uses_complete_market_of_execution_bookmaker(self):
        detail = bot.calculate_market_margin_detail(self.odds, "BTTS_YES", "B")
        self.assertEqual(detail.bookmaker, "B")
        self.assertAlmostEqual(detail.overround, (1 / 2.10) + (1 / 1.80))
        self.assertEqual(detail.prices, {"BTTS_YES": 2.10, "BTTS_NO": 1.80})

    def test_no_common_bookmaker_returns_none(self):
        broken = {
            "BTTS_YES": {"by_bookmaker": {"A": 2.0}},
            "BTTS_NO": {"by_bookmaker": {"B": 2.0}},
        }
        self.assertIsNone(bot.calculate_market_margin(broken, "BTTS_YES"))

    def test_double_chance_is_not_automatically_valued(self):
        self.assertIsNone(bot.calculate_market_margin(self.odds, "DOUBLE_1X"))


class OddsAggregationTests(unittest.TestCase):
    def test_preserves_prices_by_bookmaker(self):
        original = data_api._iter_fixture_odds
        previous = os.environ.get("BETBOT_FOOTBALL_BOOKMAKER_ALLOWLIST")
        os.environ["BETBOT_FOOTBALL_BOOKMAKER_ALLOWLIST"] = "*"
        data_api._iter_fixture_odds = lambda match: [
            {"market": "BTTS_YES", "odds": 1.9, "bookmaker": "A",
             "observed_at": "2026-07-22T12:00:00+00:00"},
            {"market": "BTTS_NO", "odds": 1.9, "bookmaker": "A",
             "observed_at": "2026-07-22T12:00:00+00:00"},
            {"market": "BTTS_YES", "odds": 2.1, "bookmaker": "B",
             "observed_at": "2026-07-22T12:00:00+00:00"},
            {"market": "BTTS_NO", "odds": 1.8, "bookmaker": "B",
             "observed_at": "2026-07-22T12:00:00+00:00"},
        ]
        try:
            result = data_api.get_odds_market_data({})
        finally:
            data_api._iter_fixture_odds = original
            if previous is None:
                os.environ.pop("BETBOT_FOOTBALL_BOOKMAKER_ALLOWLIST", None)
            else:
                os.environ["BETBOT_FOOTBALL_BOOKMAKER_ALLOWLIST"] = previous
        self.assertEqual(result["BTTS_YES"]["best_odds"], 2.1)
        self.assertEqual(result["BTTS_YES"]["by_bookmaker"], {"A": 1.9, "B": 2.1})
        self.assertIn("observed_at", result["BTTS_YES"])
        self.assertEqual(result["BTTS_YES"]["market_integrity_status"], "PASS")

    def test_rejects_wrong_over_under_scope_and_non_allowlisted_bookmaker(self):
        original = data_api.fetch_fixture_odds
        previous = os.environ.get("BETBOT_FOOTBALL_BOOKMAKER_ALLOWLIST")
        os.environ["BETBOT_FOOTBALL_BOOKMAKER_ALLOWLIST"] = "superbet,betclic"
        data_api.fetch_fixture_odds = lambda **kwargs: {
            "cached": False,
            "status_code": 200,
            "observed_at": "2026-07-26T12:00:00+00:00",
            "payload": {
                "response": [{
                    "bookmakers": [
                        {
                            "id": 1,
                            "name": "Superbet",
                            "bets": [
                                {
                                    "id": 5,
                                    "name": "Goals Over/Under",
                                    "values": [
                                        {"value": "Over 1.5", "odd": "1.45"},
                                        {"value": "Under 1.5", "odd": "2.60"},
                                        {"value": "Over 2.5", "odd": "9.50", "main": "false"},
                                    ],
                                },
                                {
                                    "id": 6,
                                    "name": "Goals Over/Under - First Half",
                                    "values": [
                                        {"value": "Over 1.5", "odd": "4.89"},
                                    ],
                                },
                                {
                                    "id": 7,
                                    "name": "Corners Over/Under",
                                    "values": [
                                        {"value": "Over 1.5", "odd": "2.85"},
                                    ],
                                },
                            ],
                        },
                        {
                            "id": 99,
                            "name": "OffshoreMax",
                            "bets": [{
                                "id": 5,
                                "name": "Goals Over/Under",
                                "values": [{"value": "Over 1.5", "odd": "9.99"}],
                            }],
                        },
                    ],
                }]
            },
        }
        try:
            rows = data_api._iter_fixture_odds({"fixture_id": 123})
        finally:
            data_api.fetch_fixture_odds = original
            if previous is None:
                os.environ.pop("BETBOT_FOOTBALL_BOOKMAKER_ALLOWLIST", None)
            else:
                os.environ["BETBOT_FOOTBALL_BOOKMAKER_ALLOWLIST"] = previous

        self.assertEqual(
            [(row["market"], row["odds"], row["bookmaker"]) for row in rows],
            [
                ("OVER_1.5", 1.45, "Superbet"),
                ("UNDER_1.5", 2.60, "Superbet"),
            ],
        )
        self.assertTrue(all(row["market_scope"] == "FULL_MATCH" for row in rows))

    def test_requested_bookmaker_has_no_cross_bookmaker_fallback(self):
        original = data_api._iter_fixture_odds
        data_api._iter_fixture_odds = lambda match: [
            {"market": "OVER_1.5", "odds": 1.91, "bookmaker": "Betclic"},
        ]
        try:
            result = data_api.get_bookmaker_market_odds(
                {"fixture_id": 123},
                "OVER_1.5",
                "superbet",
            )
        finally:
            data_api._iter_fixture_odds = original
        self.assertIsNone(result)


class FinancialSafetyTests(unittest.TestCase):
    def test_betting_is_disabled_by_default(self):
        previous = os.environ.pop("BETTING_ENABLED", None)
        try:
            self.assertFalse(execution_guard.betting_enabled())
            with self.assertRaises(execution_guard.ExecutionBlocked):
                execution_guard.assert_execution_allowed(
                    bankroll=1000,
                    requested_stake=1,
                    open_exposure=0,
                    fixture_exposure=0,
                    daily_pnl=0,
                    drawdown_fraction=0,
                    reconciliation_ok=True,
                    data_fresh=True,
                    audit_write_available=True,
                )
        finally:
            if previous is not None:
                os.environ["BETTING_ENABLED"] = previous

    def test_conservative_stake_cap(self):
        stake, _ = bot.stage_bankroll({}, 1000, 0.60, 2.0)
        self.assertLessEqual(stake, 2.50)

    def test_backup_defaults_are_per_deployment(self):
        self.assertEqual(server_data_guard.DEFAULT_BACKUP_REUSE_HOURS, 0)
        self.assertGreaterEqual(server_data_guard.DEFAULT_BACKUP_KEEP, 5)
        self.assertLessEqual(server_data_guard.DEFAULT_BACKUP_EMERGENCY_REUSE_HOURS, 24)

    def test_stale_or_unzoned_odds_are_rejected(self):
        fresh = datetime.now(timezone.utc).isoformat()
        stale = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        self.assertTrue(bot.is_fresh_observation(fresh, 300))
        self.assertFalse(bot.is_fresh_observation(stale, 300))
        self.assertFalse(bot.is_fresh_observation("2026-07-22T12:00:00", 300))

    def test_execution_identifier_includes_bookmaker_and_strategy(self):
        match = {"fixture_id": "fx-1"}
        first = bot.make_pick_id(match, "BTTS_YES", 2.0, "A", "v1")
        second = bot.make_pick_id(match, "BTTS_YES", 2.0, "B", "v1")
        third = bot.make_pick_id(match, "BTTS_YES", 2.0, "A", "v2")
        self.assertNotEqual(first, second)
        self.assertNotEqual(first, third)

    def test_container_repairs_volume_permissions_before_dropping_privileges(self):
        root = Path(__file__).resolve().parents[1]
        dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
        entrypoint = (root / "docker-entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn('ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]', dockerfile)
        self.assertIn("chown -R 10001:10001", entrypoint)
        self.assertIn('exec gosu 10001:10001 "$@"', entrypoint)

    def test_quality_process_starts_only_after_server_guard(self):
        root = Path(__file__).resolve().parents[1]
        launcher = (root / "app_launcher_quality.py").read_text(encoding="utf-8")
        self.assertLess(
            launcher.index("run_server_start_guard_once()"),
            launcher.index("subprocess.Popen("),
        )


if __name__ == "__main__":
    unittest.main()
