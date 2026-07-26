import math
import unittest

from odds_display import (
    extract_odds_snapshot,
    format_closing_clv,
    format_odds,
    format_percent,
)


class OddsDisplayTests(unittest.TestCase):
    def test_extracts_real_stored_odds_and_computes_value_and_clv(self):
        snapshot = extract_odds_snapshot(
            {
                "kurs_model": "1.72",
                "kurs_bota": "1.80",
                "kurs_buk": "2.05",
                "closing_odds": "1.95",
                "bookmaker": "Example",
            }
        )
        self.assertEqual(snapshot.model, 1.72)
        self.assertEqual(snapshot.bot, 1.80)
        self.assertEqual(snapshot.bookmaker, 2.05)
        self.assertEqual(snapshot.closing, 1.95)
        self.assertTrue(math.isclose(snapshot.value_percent, 13.888888, rel_tol=1e-5))
        self.assertTrue(math.isclose(snapshot.clv_percent, 5.128205, rel_tol=1e-5))
        self.assertEqual(format_odds(snapshot.bot), "1.80")
        self.assertEqual(format_percent(snapshot.value_percent), "+13.9%")
        self.assertEqual(format_closing_clv(snapshot), "1.95 / +5.1%")

    def test_derives_odds_only_from_explicit_probabilities(self):
        snapshot = extract_odds_snapshot(
            {"prawd_model": 0.60, "prawd_final": 55.0, "kurs_buk": 2.10}
        )
        self.assertEqual(format_odds(snapshot.model), "1.67")
        self.assertEqual(format_odds(snapshot.bot), "1.82")
        self.assertEqual(format_closing_clv(snapshot), "oczekuje")

    def test_missing_data_stays_missing_and_is_never_invented(self):
        snapshot = extract_odds_snapshot({})
        self.assertIsNone(snapshot.model)
        self.assertIsNone(snapshot.bot)
        self.assertIsNone(snapshot.bookmaker)
        self.assertEqual(format_odds(snapshot.model), "-")
        self.assertEqual(format_percent(snapshot.value_percent), "-")
        self.assertEqual(format_closing_clv(snapshot), "oczekuje")

    def test_rejects_invalid_decimal_odds_and_probabilities(self):
        snapshot = extract_odds_snapshot(
            {
                "kurs_model": 1.0,
                "kurs_bota": "nan",
                "kurs_buk": -2,
                "prawd_model": 0,
                "prawd_final": 100,
            }
        )
        self.assertIsNone(snapshot.model)
        self.assertIsNone(snapshot.bot)
        self.assertIsNone(snapshot.bookmaker)


if __name__ == "__main__":
    unittest.main()
