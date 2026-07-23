from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

import app_launcher
from server_data_guard import snapshot_hashes
from settings_v81 import ConfigurationError, load_settings
try:
    import requests as _requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.Session = object
    sys.modules["requests"] = requests_stub
from volleyball_v9.api_sports import ApiSportsVolleyballClient
from volleyball_v9.config import load_volleyball_settings
from volleyball_v9.domain import VolleyballGame
from volleyball_v9.features import (
    FeatureLeakageError,
    build_point_in_time_features,
)
from volleyball_v9.identity import normalize_name, stable_key
from volleyball_v9.model import VolleyballEloModel
from volleyball_v9.settlement import settle_match_winner
from volleyball_v9.storage import VolleyballStorage


def game(
    *,
    game_id="1",
    status="FT",
    home_sets=3,
    away_sets=1,
    scheduled_at="2026-07-20T18:00:00+00:00",
):
    return VolleyballGame(
        game_id=game_id,
        scheduled_at=scheduled_at,
        status=status,
        league_id="10",
        league_name="Test League",
        country="Poland",
        season="2026",
        home_team_id="home",
        home_team="Home",
        away_team_id="away",
        away_team="Away",
        home_sets=home_sets,
        away_sets=away_sets,
        raw={"id": game_id, "status": status},
    )


def pick_payload(game_id="1", outcome="HOME"):
    return {
        "game_id": game_id,
        "league_name": "Test League",
        "match_name": "Home vs Away",
        "market": "MATCH_WINNER",
        "outcome": outcome,
        "bookmaker": "Test Book",
        "bookmaker_odds": 2.0,
        "model_probability": 0.55,
        "model_fair_odds": 1.8182,
        "edge": 0.10,
        "confidence": 60.0,
        "model_version": "test-model",
    }


class VolleyballSettingsTests(unittest.TestCase):
    def test_default_does_not_start_volleyball(self):
        settings = load_settings({})
        self.assertFalse(settings.volleyball_enabled)
        self.assertNotIn("volleyball_shadow", app_launcher.build_process_specs(settings))

    def test_enabled_adds_only_shadow_process(self):
        settings = load_settings(
            {
                "BETBOT_VOLLEYBALL_ENABLED": "1",
                "BETBOT_VOLLEYBALL_SHADOW_ONLY": "1",
            }
        )
        specs = app_launcher.build_process_specs(settings)
        self.assertIn("volleyball_shadow", specs)
        self.assertIn("volleyball_v9.runtime", " ".join(specs["volleyball_shadow"]))

    def test_non_shadow_volleyball_is_rejected(self):
        with self.assertRaises(ConfigurationError):
            load_settings(
                {
                    "BETBOT_VOLLEYBALL_ENABLED": "1",
                    "BETBOT_VOLLEYBALL_SHADOW_ONLY": "0",
                }
            )


class VolleyballDomainTests(unittest.TestCase):
    def test_settlement_uses_sets_and_handles_void(self):
        self.assertEqual(settle_match_winner("HOME", game()), "WON")
        self.assertEqual(settle_match_winner("AWAY", game()), "LOST")
        self.assertEqual(
            settle_match_winner("HOME", game(status="CANC", home_sets=None, away_sets=None)),
            "VOID",
        )

    def test_elo_learns_without_bookmaker_odds(self):
        model = VolleyballEloModel(home_advantage=0)
        model.fit([game()])
        prediction = model.predict("home", "away")
        self.assertGreater(prediction.home_probability, 0.5)
        self.assertGreater(prediction.home_rating, prediction.away_rating)


class VolleyballStorageTests(unittest.TestCase):
    def test_storage_is_isolated_and_append_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "volleyball"
            storage = VolleyballStorage(root)
            storage.initialize()
            storage.upsert_games([game()])
            self.assertTrue(storage.db_path.is_relative_to(root))
            with storage.connect() as connection:
                sport = connection.execute("SELECT sport FROM games").fetchone()[0]
                self.assertEqual(sport, "volleyball")
                football_tables = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%football%'"
                ).fetchall()
                self.assertEqual(football_tables, [])

    def test_nested_volleyball_database_is_covered_by_server_guard(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            storage = VolleyballStorage(root / "volleyball")
            storage.initialize()
            snapshot = snapshot_hashes(root)
            self.assertIn("volleyball/volleyball_shadow.sqlite3", snapshot)

    def test_public_runtime_settings_never_contains_api_key(self):
        serialized = json.dumps(load_settings({}).public_snapshot()).lower()
        self.assertNotIn("volleyball_api_sports_key", serialized)
        self.assertNotIn("api_key", serialized)

    def test_coverage_counts_only_inserted_odds(self):
        from volleyball_v9.domain import OddsQuote
        with tempfile.TemporaryDirectory() as temporary:
            storage = VolleyballStorage(Path(temporary) / "volleyball")
            storage.initialize()
            upcoming = game(status="NS", home_sets=None, away_sets=None)
            storage.upsert_games([upcoming])
            quote = OddsQuote(
                game_id=upcoming.game_id,
                bookmaker_id="1",
                bookmaker="Test",
                market="MATCH_WINNER",
                outcome="HOME",
                odds=1.90,
                observed_at="2026-07-23T12:00:00+00:00",
            )
            self.assertEqual(storage.save_odds([quote]), 1)
            self.assertEqual(storage.save_odds([quote]), 0)
            coverage = storage.coverage_summary()
            self.assertEqual(coverage["odds_quotes"], 1)
            self.assertEqual(coverage["games_with_odds"], 1)

    def test_identities_are_stable_and_created_for_valid_games(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = VolleyballStorage(Path(temporary) / "volleyball")
            storage.initialize()
            self.assertEqual(storage.upsert_games([game()]), 1)
            with storage.connect() as connection:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM team_identities").fetchone()[0],
                    2,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM league_identities").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM game_identities").fetchone()[0],
                    1,
                )
            self.assertEqual(
                stable_key("team", "home", "Home"),
                stable_key("team", "home", "Renamed Home"),
            )
            self.assertEqual(normalize_name("  Śląsk   Wrocław "), "śląsk wrocław")

    def test_invalid_and_duplicate_games_are_quarantined_append_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = VolleyballStorage(Path(temporary) / "volleyball")
            storage.initialize()
            valid = game(game_id="valid")
            duplicate = VolleyballGame(
                **{**valid.__dict__, "game_id": "duplicate", "raw": {"id": "duplicate"}}
            )
            invalid = VolleyballGame(
                **{
                    **valid.__dict__,
                    "game_id": "invalid",
                    "away_team_id": valid.home_team_id,
                    "away_team": valid.home_team,
                    "raw": {"id": "invalid"},
                }
            )
            self.assertEqual(storage.upsert_games([valid, duplicate, invalid]), 1)
            with storage.connect() as connection:
                rows = connection.execute(
                    "SELECT quarantine_key, reason FROM identity_quarantine ORDER BY reason"
                ).fetchall()
                self.assertEqual(len(rows), 2)
                reasons = " ".join(row["reason"] for row in rows)
                self.assertIn("duplicate_fingerprint", reasons)
                self.assertIn("same_team_id", reasons)
                with self.assertRaises(Exception):
                    connection.execute(
                        "DELETE FROM identity_quarantine WHERE quarantine_key=?",
                        (rows[0]["quarantine_key"],),
                    )

    def test_initialize_backfills_identities_for_existing_v91_games(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = VolleyballStorage(Path(temporary) / "volleyball")
            storage.initialize()
            storage.upsert_games([game(game_id="legacy")])
            with storage.connect() as connection:
                connection.execute("DELETE FROM game_identities WHERE game_id='legacy'")
            storage.initialize()
            with storage.connect() as connection:
                count = connection.execute(
                    "SELECT COUNT(*) FROM game_identities WHERE game_id='legacy'"
                ).fetchone()[0]
            self.assertEqual(count, 1)

    def test_open_pick_dates_keep_old_matches_in_result_window(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = VolleyballStorage(Path(temporary) / "volleyball")
            storage.initialize()
            pending = game(
                game_id="pending", status="NS", home_sets=None, away_sets=None
            )
            storage.upsert_games([pending])
            storage.create_shadow_pick(pick_payload(game_id="pending"))
            self.assertEqual(storage.open_pick_dates(), ["2026-07-20"])

    def test_settlement_is_idempotent_and_audited_append_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = VolleyballStorage(Path(temporary) / "volleyball")
            storage.initialize()
            finished = game(game_id="settle")
            storage.upsert_games([finished])
            storage.create_shadow_pick(pick_payload(game_id="settle"))
            pick = storage.open_picks()[0]
            self.assertTrue(
                storage.close_pick(pick["pick_key"], "WON", 1.0, finished)
            )
            self.assertFalse(
                storage.close_pick(pick["pick_key"], "WON", 1.0, finished)
            )
            closed = storage.closed_picks()[0]
            inserted, status = storage.record_settlement_audit(
                closed, finished, "WON"
            )
            self.assertTrue(inserted)
            self.assertEqual(status, "CONSISTENT")
            inserted_again, _ = storage.record_settlement_audit(
                closed, finished, "WON"
            )
            self.assertFalse(inserted_again)
            inserted_mismatch, mismatch_status = storage.record_settlement_audit(
                closed, finished, "LOST"
            )
            self.assertTrue(inserted_mismatch)
            self.assertEqual(mismatch_status, "MISMATCH")
            with storage.connect() as connection:
                summary = connection.execute(
                    """
                    SELECT COUNT(*) AS total,
                           SUM(CASE WHEN audit_status='MISMATCH' THEN 1 ELSE 0 END) AS bad
                    FROM settlement_audit
                    """
                ).fetchone()
                self.assertEqual(summary["total"], 2)
                self.assertEqual(summary["bad"], 1)
                with self.assertRaises(Exception):
                    connection.execute("DELETE FROM settlement_audit")

    def test_point_in_time_training_excludes_future_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = VolleyballStorage(Path(temporary) / "volleyball")
            storage.initialize()
            past = game(
                game_id="past",
                scheduled_at="2026-12-01T18:00:00+00:00",
            )
            future_result = game(
                game_id="future-result",
                scheduled_at="2026-12-06T18:00:00+00:00",
            )
            target = game(
                game_id="target",
                status="NS",
                home_sets=None,
                away_sets=None,
                scheduled_at="2026-12-10T18:00:00+00:00",
            )
            storage.upsert_games([past, future_result, target])
            training, metadata = storage.point_in_time_training_set(
                target, "2026-12-05T12:00:00+00:00"
            )
            self.assertEqual([item.game_id for item in training], ["past"])
            self.assertEqual(metadata["source_games"], 1)
            self.assertLess(
                metadata["source_max_scheduled_at"],
                "2026-12-05T12:00:00+00:00",
            )

    def test_feature_snapshot_is_point_in_time_and_append_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = VolleyballStorage(Path(temporary) / "volleyball")
            storage.initialize()
            past = game(
                game_id="feature-past",
                scheduled_at="2026-12-01T18:00:00+00:00",
            )
            target = game(
                game_id="feature-target",
                status="NS",
                home_sets=None,
                away_sets=None,
                scheduled_at="2026-12-10T18:00:00+00:00",
            )
            storage.upsert_games([past, target])
            observed_at = "2026-12-05T12:00:00+00:00"
            training, metadata = storage.point_in_time_training_set(
                target, observed_at
            )
            bundle = build_point_in_time_features(
                target,
                training,
                observed_at=observed_at,
                model_version="test-pit-model",
                source_metadata=metadata,
            )
            inserted, feature_key, status = storage.record_feature_snapshot(
                bundle.payload
            )
            self.assertTrue(inserted)
            self.assertEqual(status, "PASS")
            self.assertTrue(feature_key)
            inserted_again, same_key, _ = storage.record_feature_snapshot(
                bundle.payload
            )
            self.assertFalse(inserted_again)
            self.assertEqual(same_key, feature_key)
            linked_pick = pick_payload(game_id=target.game_id)
            linked_pick["feature_key"] = feature_key
            linked_pick["feature_schema"] = bundle.payload["feature_schema"]
            self.assertTrue(storage.create_shadow_pick(linked_pick))
            with storage.connect() as connection:
                row = connection.execute(
                    "SELECT * FROM feature_snapshots WHERE feature_key=?",
                    (feature_key,),
                ).fetchone()
                self.assertLess(row["source_max_scheduled_at"], row["feature_cutoff_at"])
                self.assertLessEqual(row["source_max_observed_at"], row["observed_at"])
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM pick_feature_links WHERE feature_key=?",
                        (feature_key,),
                    ).fetchone()[0],
                    1,
                )
                with self.assertRaises(Exception):
                    connection.execute(
                        "UPDATE feature_snapshots SET confidence=99 WHERE feature_key=?",
                        (feature_key,),
                    )

    def test_feature_leakage_is_blocked_and_quarantined(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = VolleyballStorage(Path(temporary) / "volleyball")
            storage.initialize()
            target = game(
                game_id="leak-target",
                status="NS",
                home_sets=None,
                away_sets=None,
                scheduled_at="2026-12-10T18:00:00+00:00",
            )
            storage.upsert_games([target])
            with self.assertRaises(FeatureLeakageError):
                build_point_in_time_features(
                    target,
                    [],
                    observed_at="2026-12-10T18:00:00+00:00",
                    model_version="test-pit-model",
                    source_metadata={"source_games": 0},
                )
            valid = build_point_in_time_features(
                target,
                [],
                observed_at="2026-12-05T12:00:00+00:00",
                model_version="test-pit-model",
                source_metadata={"source_games": 0},
            ).payload
            invalid = {
                **valid,
                "source_games": 1,
                "source_max_scheduled_at": "2026-12-06T12:00:00+00:00",
                "source_max_observed_at": "2026-12-06T12:00:00+00:00",
            }
            inserted, feature_key, status = storage.record_feature_snapshot(invalid)
            self.assertFalse(inserted)
            self.assertFalse(feature_key)
            self.assertEqual(status, "BLOCKED")
            coverage = storage.coverage_summary()
            self.assertEqual(coverage["feature_snapshots"], 0)
            self.assertEqual(coverage["feature_quarantined"], 1)
            self.assertEqual(coverage["feature_leakage_rate"], 1.0)

    def test_v94_migration_preserves_existing_v93_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = VolleyballStorage(Path(temporary) / "volleyball")
            storage.initialize()
            existing = game(
                game_id="v93-existing",
                status="NS",
                home_sets=None,
                away_sets=None,
            )
            storage.upsert_games([existing])
            storage.create_shadow_pick(pick_payload(game_id=existing.game_id))
            with storage.connect() as connection:
                connection.execute("DROP TABLE pick_feature_links")
                connection.execute("DROP TABLE feature_quarantine")
                connection.execute("DROP TABLE feature_snapshots")
            storage.initialize()
            with storage.connect() as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM games WHERE game_id='v93-existing'"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM shadow_picks WHERE game_id='v93-existing'"
                    ).fetchone()[0],
                    1,
                )
                tables = {
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name LIKE 'feature_%'
                        """
                    ).fetchall()
                }
                self.assertEqual(
                    tables, {"feature_snapshots", "feature_quarantine"}
                )


class _FakeResponse:
    def __init__(self, status_code, payload, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, *args, **kwargs):
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


class VolleyballProviderTests(unittest.TestCase):
    def test_retry_is_bounded_and_observed(self):
        observed = []
        settings = load_volleyball_settings(require_key=False)
        session = _FakeSession(
            [
                _FakeResponse(500, {}),
                _FakeResponse(
                    200,
                    {"errors": [], "response": [{"id": 1}]},
                    {"x-ratelimit-requests-remaining": "99"},
                ),
            ]
        )
        client = ApiSportsVolleyballClient(
            settings, session=session, observer=observed.append
        )
        rows = client._get("games", {"date": "2026-07-23"})
        self.assertEqual(rows, [{"id": 1}])
        self.assertEqual(session.calls, 2)
        self.assertEqual(len(observed), 2)
        self.assertEqual(observed[0]["status"], "RETRY")
        self.assertEqual(observed[-1]["status"], "SUCCESS")
        self.assertEqual(observed[-1]["remaining"], 99)


if __name__ == "__main__":
    unittest.main()
