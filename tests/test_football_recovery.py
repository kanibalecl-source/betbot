from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

import pandas as pd

import ai_self_learning_runtime
import data_api


NOW = "2026-10-17T17:00:00Z"


def odds_event():
    return {
        "id": "odds-event-1",
        "commence_time": "2026-10-17T18:00:00Z",
        "home_team": "Legia Warszawa",
        "away_team": "Lech Poznan",
        "bookmakers": [
            {
                "key": "superbet",
                "title": "Superbet",
                "last_update": NOW,
                "markets": [
                    {
                        "key": "h2h",
                        "last_update": NOW,
                        "outcomes": [
                            {"name": "Legia Warszawa", "price": 2.1},
                            {"name": "Draw", "price": 3.3},
                            {"name": "Lech Poznan", "price": 3.4},
                        ],
                    },
                    {
                        "key": "totals",
                        "last_update": NOW,
                        "outcomes": [
                            {"name": "Over", "point": 2.5, "price": 1.9},
                            {"name": "Under", "point": 2.5, "price": 1.95},
                        ],
                    },
                ],
            }
        ],
    }


class FootballOddsFallbackTests(unittest.TestCase):
    def setUp(self):
        data_api.THE_ODDS_API_CACHE.clear()

    def test_real_second_source_is_cached_per_competition(self):
        response = Mock()
        response.status_code = 200
        response.headers = {"x-requests-remaining": "999"}
        response.json.return_value = [odds_event()]
        match = {
            "fixture_id": 1,
            "league_id": 106,
            "home": "Legia Warszawa",
            "away": "Lech Poznań",
            "match_date": "2026-10-17T18:00:00+00:00",
        }
        with patch.dict(os.environ, {"ODDS_API_KEY": "real-key"}, clear=False), patch.object(
            data_api.requests, "get", return_value=response
        ) as request:
            first = data_api._iter_the_odds_api_rows(match)
            second = data_api._iter_the_odds_api_rows(match)

        self.assertEqual(request.call_count, 1)
        self.assertEqual(first, second)
        self.assertEqual({row["bookmaker"] for row in first}, {"Superbet"})
        self.assertIn("HOME_WIN", {row["market"] for row in first})
        self.assertIn("OVER_2.5", {row["market"] for row in first})

    def test_event_mapping_fails_closed_when_identity_is_ambiguous(self):
        match = {
            "fixture_id": 1,
            "home": "Legia Warszawa",
            "away": "Lech Poznan",
            "match_date": "2026-10-17T18:00:00Z",
        }
        self.assertIsNone(
            data_api._matching_the_odds_event(match, [odds_event(), odds_event()])
        )

    def test_missing_key_does_not_call_network(self):
        with patch.dict(
            os.environ, {"ODDS_API_KEY": "", "THE_ODDS_API_KEY": ""}, clear=False
        ), patch.object(data_api.requests, "get") as request:
            self.assertEqual(data_api._the_odds_api_events("soccer_epl"), [])
        request.assert_not_called()


class AiCandidateRecoveryTests(unittest.TestCase):
    def test_legacy_rows_without_pick_id_are_not_current_candidates(self):
        legacy = pd.DataFrame([{"fixture_id": "1", "market": "OVER_2.5"}])
        fresh = pd.DataFrame(
            [{"fixture_id": "2", "pick_id": "p-2", "market": "OVER_2.5"}]
        )
        with patch.object(
            ai_self_learning_runtime, "read_csv", side_effect=[legacy, fresh]
        ):
            result = ai_self_learning_runtime.candidates()
        self.assertEqual(result["pick_id"].tolist(), ["p-2"])


if __name__ == "__main__":
    unittest.main()
