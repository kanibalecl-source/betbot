import math
import os
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone


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
        data_api._iter_fixture_odds = lambda match: [
            {"market": "BTTS_YES", "odds": 1.9, "bookmaker": "A"},
            {"market": "BTTS_YES", "odds": 2.1, "bookmaker": "B"},
        ]
        try:
            result = data_api.get_odds_market_data({})
        finally:
            data_api._iter_fixture_odds = original
        self.assertEqual(result["BTTS_YES"]["best_odds"], 2.1)
        self.assertEqual(result["BTTS_YES"]["by_bookmaker"], {"A": 1.9, "B": 2.1})
        self.assertIn("observed_at", result["BTTS_YES"])


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


if __name__ == "__main__":
    unittest.main()
