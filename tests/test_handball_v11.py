from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
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
from handball_v11.api_sports import ApiSportsHandballClient
from handball_v11.config import load_handball_settings
from handball_v11.domain import OddsQuote, HandballGame
from handball_v11.features import (
    FeatureLeakageError,
    build_point_in_time_features,
)
from handball_v11.governor import (
    GovernorSettings,
    build_live_shadow_report,
    run_autonomous_governor,
)
from handball_v11.identity import normalize_name, stable_key
from handball_v11.market import (
    build_no_vig_consensus,
    eligible_match_winner_quotes,
)
from handball_v11.model import HandballEloModel
from handball_v11.runtime import run_cycle
from handball_v11.settlement import settle_match_winner
from handball_v11.storage import HandballStorage
from handball_v11.training import (
    DEFAULT_HYPERPARAMETERS,
    HYPERPARAMETER_GRID,
    build_training_dataset,
    train_candidate,
    tune_hyperparameters,
    verify_candidate,
)
from handball_v11.validation import (
    ValidationSettings,
    build_walk_forward_folds,
    validate_candidate,
)


def game(
    *,
    game_id="1",
    status="FT",
    home_goals=3,
    away_goals=1,
    scheduled_at="2026-07-20T18:00:00+00:00",
):
    return HandballGame(
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
        home_goals=home_goals,
        away_goals=away_goals,
        raw={"id": game_id, "status": status},
    )


def pick_payload(game_id="1", outcome="HOME"):
    return {
        "game_id": game_id,
        "league_name": "Test League",
        "match_name": "Home vs Away",
        "market": "MATCH_WINNER_NO_DRAW",
        "outcome": outcome,
        "bookmaker": "Test Book",
        "bookmaker_odds": 2.0,
        "model_probability": 0.55,
        "model_fair_odds": 1.8182,
        "edge": 0.10,
        "confidence": 60.0,
        "model_version": "test-model",
    }


def quote(
    bookmaker_id,
    outcome,
    odds,
    *,
    game_id="market",
    observed_at="2026-12-05T12:00:00+00:00",
):
    return OddsQuote(
        game_id=game_id,
        bookmaker_id=str(bookmaker_id),
        bookmaker=f"Book {bookmaker_id}",
        market="MATCH_WINNER_NO_DRAW",
        outcome=outcome,
        odds=odds,
        observed_at=observed_at,
    )


def training_game(index: int) -> HandballGame:
    return HandballGame(
        game_id=f"training-{index}",
        scheduled_at=f"2026-01-{index + 1:02d}T18:00:00+00:00",
        status="FT",
        league_id="training-league",
        league_name="Training League",
        country="Poland",
        season="2026",
        home_team_id=f"team-{index % 3}",
        home_team=f"Team {index % 3}",
        away_team_id=f"team-{(index + 1) % 3}",
        away_team=f"Team {(index + 1) % 3}",
        home_goals=3 if index % 2 == 0 else 1,
        away_goals=1 if index % 2 == 0 else 3,
        raw={
            "private_provider_payload": f"raw-{index}",
            "bookmaker_odds": 9.99,
        },
    )


def validation_game(index: int) -> HandballGame:
    scheduled = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=index)
    home = f"validation-team-{index % 6}"
    away = f"validation-team-{(index + 1) % 6}"
    return HandballGame(
        game_id=f"validation-{index}",
        scheduled_at=scheduled.isoformat(),
        status="FT",
        league_id=f"league-{index % 2}",
        league_name="Validation League",
        country="Poland",
        season="2026",
        home_team_id=home,
        home_team=home,
        away_team_id=away,
        away_team=away,
        home_goals=3 if index % 3 else 1,
        away_goals=1 if index % 3 else 3,
        raw={},
    )


def live_game(index: int, *, finished: bool) -> HandballGame:
    scheduled = datetime(2027, 1, 1, tzinfo=timezone.utc) + timedelta(days=index)
    return HandballGame(
        game_id=f"live-{index}",
        scheduled_at=scheduled.isoformat(),
        status="FT" if finished else "NS",
        league_id=f"live-league-{index % 2}",
        league_name="Live League",
        country="Poland",
        season="2027",
        home_team_id=f"live-home-{index % 5}",
        home_team=f"Live Home {index % 5}",
        away_team_id=f"live-away-{index % 5}",
        away_team=f"Live Away {index % 5}",
        home_goals=3 if finished else None,
        away_goals=1 if finished else None,
        raw={},
    )


class HandballSettingsTests(unittest.TestCase):
    def test_default_does_not_start_handball(self):
        settings = load_settings({})
        self.assertFalse(settings.handball_enabled)
        self.assertNotIn("handball_shadow", app_launcher.build_process_specs(settings))

    def test_collection_poll_defaults_to_thirty_minutes(self):
        settings = load_settings({})
        self.assertEqual(settings.handball_poll_minutes, 30)
        overridden = load_settings({"BETBOT_HANDBALL_POLL_MINUTES": "45"})
        self.assertEqual(overridden.handball_poll_minutes, 45)

    def test_enabled_adds_only_shadow_process(self):
        settings = load_settings(
            {
                "BETBOT_HANDBALL_ENABLED": "1",
                "BETBOT_HANDBALL_SHADOW_ONLY": "1",
            }
        )
        specs = app_launcher.build_process_specs(settings)
        self.assertIn("handball_shadow", specs)
        self.assertIn("handball_v11.runtime", " ".join(specs["handball_shadow"]))

    def test_non_shadow_handball_is_rejected(self):
        with self.assertRaises(ConfigurationError):
            load_settings(
                {
                    "BETBOT_HANDBALL_ENABLED": "1",
                    "BETBOT_HANDBALL_SHADOW_ONLY": "0",
                }
            )

    def test_v115_requires_two_bookmakers_by_default(self):
        self.assertEqual(
            load_handball_settings(require_key=False).minimum_bookmakers,
            2,
        )

    def test_v116_requires_minimum_training_sample_by_default(self):
        settings = load_handball_settings(require_key=False)
        self.assertEqual(settings.training_min_games, 100)
        self.assertEqual(settings.training_min_new_games, 25)

    def test_v117_walk_forward_defaults_are_conservative(self):
        settings = load_handball_settings(require_key=False)
        self.assertEqual(settings.validation_min_train_games, 40)
        self.assertEqual(settings.validation_min_test_games, 20)
        self.assertEqual(settings.validation_min_folds, 3)
        self.assertEqual(settings.validation_max_folds, 5)

    def test_v10_autonomous_shadow_defaults_are_safe(self):
        settings = load_handball_settings(require_key=False)
        self.assertTrue(settings.autonomous_governor_enabled)
        self.assertEqual(settings.live_shadow_min_samples, 30)
        self.assertEqual(settings.live_shadow_positive_reports, 3)
        self.assertEqual(settings.live_shadow_rollback_reports, 3)
        self.assertAlmostEqual(settings.live_shadow_drift_psi_limit, 0.25)


class HandballDomainTests(unittest.TestCase):
    def test_settlement_uses_goals_and_handles_void(self):
        self.assertEqual(settle_match_winner("HOME", game()), "WON")
        self.assertEqual(settle_match_winner("AWAY", game()), "LOST")
        self.assertEqual(
            settle_match_winner("HOME", game(status="CANC", home_goals=None, away_goals=None)),
            "VOID",
        )
        self.assertEqual(
            settle_match_winner("HOME", game(home_goals=28, away_goals=28)),
            "VOID",
        )

    def test_elo_learns_without_bookmaker_odds(self):
        model = HandballEloModel(home_advantage=0)
        model.fit([game()])
        prediction = model.predict("home", "away")
        self.assertGreater(prediction.home_probability, 0.5)
        self.assertGreater(prediction.home_rating, prediction.away_rating)

    def test_no_vig_consensus_uses_only_complete_valid_bookmaker_pairs(self):
        quotes = [
            quote("one", "HOME", 1.80),
            quote("one", "AWAY", 2.20),
            quote("two", "HOME", 1.90),
            quote("two", "AWAY", 2.00),
            quote("incomplete", "HOME", 99.0),
            quote("invalid", "HOME", 1.01),
            quote("invalid", "AWAY", 1.01),
        ]
        eligible = eligible_match_winner_quotes(quotes)
        self.assertEqual({item.bookmaker_id for item in eligible}, {"one", "two"})
        consensus = build_no_vig_consensus(quotes)
        self.assertIsNotNone(consensus)
        self.assertEqual(consensus.bookmaker_count, 2)
        self.assertAlmostEqual(
            consensus.home_probability + consensus.away_probability,
            1.0,
            places=7,
        )
        self.assertEqual(consensus.best_home_odds, 1.90)
        self.assertEqual(consensus.best_away_odds, 2.20)
        self.assertGreaterEqual(consensus.probability_dispersion, 0.0)

    def test_single_book_market_is_explicit_class_c_shadow_only(self):
        consensus = build_no_vig_consensus(
            [
                quote("one", "HOME", 1.80),
                quote("one", "AWAY", 2.20),
            ]
        )
        self.assertIsNotNone(consensus)
        payload = consensus.payload()
        self.assertEqual(payload["bookmaker_count"], 1)
        self.assertEqual(payload["source_bookmakers"], ["one"])
        self.assertEqual(payload["market_quality_tier"], "C_SINGLE_BOOK_SHADOW")
        self.assertTrue(payload["shadow_observation_only"])
        self.assertFalse(payload["training_eligible"])
        self.assertFalse(payload["pick_eligible"])
        self.assertFalse(payload["promotion_eligible"])
        self.assertTrue(payload["de_vig_applied"])

    def test_candidate_artifact_is_reproducible_and_odds_free(self):
        games = [training_game(index) for index in range(5)]
        first = train_candidate(games, minimum_rows=5)
        second = train_candidate(reversed(games), minimum_rows=5)
        self.assertEqual(first.status, "CANDIDATE_READY")
        self.assertTrue(first.reproducible)
        self.assertTrue(verify_candidate(first))
        self.assertEqual(first.dataset_sha256, second.dataset_sha256)
        self.assertEqual(first.artifact_sha256, second.artifact_sha256)
        self.assertEqual(first.candidate_id, second.candidate_id)
        serialized = json.dumps(first.dataset_document).lower()
        self.assertNotIn("bookmaker_odds", serialized)
        self.assertNotIn("private_provider_payload", serialized)
        self.assertFalse(first.artifact["active_model_modified"])
        self.assertEqual(first.artifact["algorithm"], "tuned_chronological_elo")
        self.assertIn(first.artifact["hyperparameters"], HYPERPARAMETER_GRID)
        self.assertFalse(first.artifact["tuning"]["bookmaker_data_used"])

    def test_v10_tuning_is_deterministic_and_time_safe(self):
        games = [validation_game(index) for index in range(100)]
        first_parameters, first_report = tune_hyperparameters(games)
        second_parameters, second_report = tune_hyperparameters(list(reversed(games)))
        self.assertEqual(first_parameters, second_parameters)
        self.assertEqual(first_report, second_report)
        self.assertEqual(first_report["status"], "TUNED_TIME_SAFE")
        self.assertLess(
            first_report["training_end_timestamp"],
            first_report["validation_start_timestamp"],
        )
        self.assertFalse(first_report["bookmaker_data_used"])

    def test_candidate_waits_for_minimum_sample(self):
        candidate = train_candidate(
            [training_game(0), training_game(1)],
            minimum_rows=3,
        )
        self.assertEqual(candidate.status, "WAITING_MINIMUM_SAMPLE")
        self.assertEqual(candidate.dataset_rows, 2)
        self.assertFalse(candidate.reproducible)


class HandballWalkForwardTests(unittest.TestCase):
    def _candidate(self, count=100):
        bundle = train_candidate(
            [validation_game(index) for index in range(count)],
            minimum_rows=count,
        )
        self.assertTrue(bundle.reproducible)
        return bundle.payload()

    def test_validation_waits_without_reproducible_candidate(self):
        report = validate_candidate(None)
        self.assertEqual(report["status"], "WAITING_REPRODUCIBLE_CANDIDATE")
        self.assertFalse(report["automatic_promotion"])
        self.assertFalse(report["active_model_modified"])

    def test_folds_are_strictly_chronological(self):
        games = [validation_game(index) for index in range(100)]
        settings = ValidationSettings(
            minimum_train_rows=40,
            minimum_test_rows=20,
            minimum_folds=3,
            maximum_folds=5,
            bootstrap_samples=100,
        )
        folds = build_walk_forward_folds(games, settings)
        self.assertEqual(len(folds), 3)
        for training, testing in folds:
            self.assertLess(
                max(item.scheduled_at for item in training),
                min(item.scheduled_at for item in testing),
            )

    def test_equal_timestamp_is_never_split_across_fold_boundary(self):
        games = [validation_game(index) for index in range(100)]
        paired = []
        for index, item in enumerate(games):
            paired.append(
                HandballGame(
                    **{
                        **item.__dict__,
                        "scheduled_at": games[index - index % 2].scheduled_at,
                    }
                )
            )
        folds = build_walk_forward_folds(
            paired,
            ValidationSettings(
                minimum_train_rows=40,
                minimum_test_rows=20,
                minimum_folds=3,
                maximum_folds=5,
                bootstrap_samples=100,
            ),
        )
        for training, testing in folds:
            self.assertNotEqual(
                training[-1].scheduled_at,
                testing[0].scheduled_at,
            )

    def test_identical_challenger_is_rejected_and_never_promoted(self):
        candidate = self._candidate()
        candidate["artifact"]["hyperparameters"] = dict(DEFAULT_HYPERPARAMETERS)
        candidate["artifact"]["algorithm"] = "chronological_elo"
        report = validate_candidate(
            candidate,
            settings=ValidationSettings(bootstrap_samples=200),
        )
        self.assertEqual(report["folds"], 3)
        self.assertEqual(report["oos_samples"], 60)
        self.assertEqual(report["status"], "REJECTED_OR_REVIEW")
        self.assertFalse(report["positive_validation"])
        self.assertFalse(report["automatic_promotion"])
        self.assertTrue(report["manual_approval_required"])
        self.assertFalse(report["active_model_modified"])
        self.assertEqual(report["brier_improvement"], 0.0)
        self.assertEqual(report["log_loss_improvement"], 0.0)
        self.assertTrue(report["gates"]["chronological_no_leakage"])

    def test_insufficient_candidate_never_passes(self):
        report = validate_candidate(
            self._candidate(60),
            settings=ValidationSettings(
                minimum_train_rows=40,
                minimum_test_rows=20,
                minimum_folds=3,
                maximum_folds=5,
                bootstrap_samples=100,
            ),
        )
        self.assertEqual(report["status"], "NO_ENOUGH_DATA")
        self.assertFalse(report["positive_validation"])
        self.assertFalse(report["automatic_promotion"])


class HandballV10GovernorTests(unittest.TestCase):
    def _registered_candidate(self, storage):
        training = [validation_game(index) for index in range(100)]
        storage.upsert_games(training)
        bundle = train_candidate(training, minimum_rows=100)
        inserted, candidate_id = storage.register_model_candidate(bundle.payload())
        self.assertTrue(inserted)
        candidate = storage.model_candidate(candidate_id)
        self.assertIsNotNone(candidate)
        return candidate

    def _settled_pair_evidence(
        self,
        storage,
        candidate,
        count=30,
        *,
        start=0,
        challenger_probability=0.85,
    ):
        observed_at = "2026-12-01T00:00:00+00:00"
        upcoming = [
            live_game(index, finished=False)
            for index in range(start, start + count)
        ]
        storage.upsert_games(upcoming)
        for item in upcoming:
            inserted, _ = storage.record_live_prediction(
                candidate_id=candidate["candidate_id"],
                comparator_model_id="BASELINE",
                role="CHAMPION",
                game=item,
                observed_at=observed_at,
                home_probability=0.50,
                model_parameters=DEFAULT_HYPERPARAMETERS,
            )
            self.assertTrue(inserted)
            inserted, _ = storage.record_live_prediction(
                candidate_id=candidate["candidate_id"],
                comparator_model_id=candidate["candidate_id"],
                role="CHALLENGER",
                game=item,
                observed_at=observed_at,
                home_probability=challenger_probability,
                model_parameters=candidate["artifact"]["hyperparameters"],
            )
            self.assertTrue(inserted)
        finished = [
            live_game(index, finished=True)
            for index in range(start, start + count)
        ]
        storage.upsert_games(finished)
        self.assertEqual(storage.settle_live_predictions(finished), count * 2)

    def test_governor_waits_without_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            result = run_autonomous_governor(
                storage,
                [],
                None,
                None,
            )
            self.assertEqual(result["status"], "WAITING_REPRODUCIBLE_CANDIDATE")
            self.assertFalse(result["shadow_model_changed"])
            self.assertFalse(result["real_execution_allowed"])

    def test_live_shadow_report_uses_paired_future_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            candidate = self._registered_candidate(storage)
            self._settled_pair_evidence(storage, candidate)
            report = build_live_shadow_report(
                storage,
                candidate,
                GovernorSettings(
                    minimum_live_samples=30,
                    drift_psi_limit=100.0,
                    bootstrap_samples=200,
                ),
            )
            self.assertEqual(report["status"], "POSITIVE_LIVE_SHADOW")
            self.assertTrue(report["positive"])
            self.assertGreater(report["brier_improvement"], 0)
            self.assertGreater(report["log_loss_improvement"], 0)
            self.assertTrue(report["gates"]["segment_stability"])
            self.assertFalse(report["real_execution_allowed"])

    def test_governor_promotes_only_after_repeated_positive_live_reports(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            candidate = self._registered_candidate(storage)
            validation = {"status": "POSITIVE_VALIDATION_MANUAL_APPROVAL"}
            settings = GovernorSettings(
                minimum_live_samples=30,
                report_step_samples=10,
                required_positive_reports=3,
                rollback_negative_reports=3,
                drift_psi_limit=100.0,
                bootstrap_samples=100,
            )
            statuses = []
            for start, count in ((0, 30), (30, 10), (40, 10)):
                self._settled_pair_evidence(
                    storage,
                    candidate,
                    count=count,
                    start=start,
                )
                result = run_autonomous_governor(
                    storage,
                    storage.load_games(),
                    candidate,
                    validation,
                    settings=settings,
                )
                statuses.append(result["status"])
            self.assertEqual(
                statuses[:2],
                [
                    "WAITING_REPEATED_POSITIVE_LIVE_REPORTS",
                    "WAITING_REPEATED_POSITIVE_LIVE_REPORTS",
                ],
            )
            self.assertEqual(statuses[2], "PROMOTED_SHADOW")
            self.assertEqual(
                storage.active_shadow_model_id(),
                candidate["candidate_id"],
            )
            self.assertFalse(result["real_execution_allowed"])

    def test_shadow_promotion_and_rollback_are_append_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            candidate = self._registered_candidate(storage)
            promoted, promotion_id = storage.record_lifecycle_event(
                candidate_id=candidate["candidate_id"],
                event_type="PROMOTED_SHADOW",
                previous_model_id="BASELINE",
                evidence_report_id="report-positive",
                reason="test_positive_evidence",
            )
            self.assertTrue(promoted)
            self.assertTrue(promotion_id)
            self.assertEqual(
                storage.active_shadow_model_id(),
                candidate["candidate_id"],
            )
            rolled_back, rollback_id = storage.record_lifecycle_event(
                candidate_id=candidate["candidate_id"],
                event_type="ROLLED_BACK_SHADOW",
                previous_model_id="BASELINE",
                evidence_report_id="report-negative",
                reason="test_regression",
            )
            self.assertTrue(rolled_back)
            self.assertTrue(rollback_id)
            self.assertEqual(storage.active_shadow_model_id(), "BASELINE")
            coverage = storage.coverage_summary()
            self.assertEqual(coverage["shadow_model_promotions"], 1)
            self.assertEqual(coverage["shadow_model_rollbacks"], 1)
            self.assertTrue(coverage["live_registry_integrity"])
            with storage.connect() as connection:
                with self.assertRaises(Exception):
                    connection.execute("DELETE FROM model_lifecycle_events")

    def test_live_prediction_and_settlement_are_immutable(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            candidate = self._registered_candidate(storage)
            self._settled_pair_evidence(storage, candidate, count=1)
            with storage.connect() as connection:
                with self.assertRaises(Exception):
                    connection.execute(
                        "UPDATE model_live_predictions SET home_probability=0.1"
                    )
                with self.assertRaises(Exception):
                    connection.execute("DELETE FROM model_live_settlements")


class HandballStorageTests(unittest.TestCase):
    def test_storage_is_isolated_and_append_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "handball"
            storage = HandballStorage(root)
            storage.initialize()
            storage.upsert_games([game()])
            self.assertTrue(storage.db_path.is_relative_to(root))
            with storage.connect() as connection:
                sport = connection.execute("SELECT sport FROM games").fetchone()[0]
                self.assertEqual(sport, "handball")
                football_tables = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%football%'"
                ).fetchall()
                self.assertEqual(football_tables, [])

    def test_nested_handball_database_is_covered_by_server_guard(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            storage = HandballStorage(root / "handball")
            storage.initialize()
            snapshot = snapshot_hashes(root)
            self.assertIn("handball/handball_shadow.sqlite3", snapshot)

    def test_public_runtime_settings_never_contains_api_key(self):
        serialized = json.dumps(load_settings({}).public_snapshot()).lower()
        self.assertNotIn("handball_api_sports_key", serialized)
        self.assertNotIn("api_key", serialized)

    def test_coverage_counts_only_inserted_odds(self):
        from handball_v11.domain import OddsQuote
        with tempfile.TemporaryDirectory() as temporary:
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            upcoming = game(status="NS", home_goals=None, away_goals=None)
            storage.upsert_games([upcoming])
            quote = OddsQuote(
                game_id=upcoming.game_id,
                bookmaker_id="1",
                bookmaker="Test",
                market="MATCH_WINNER_NO_DRAW",
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
            storage = HandballStorage(Path(temporary) / "handball")
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
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            valid = game(game_id="valid")
            duplicate = HandballGame(
                **{**valid.__dict__, "game_id": "duplicate", "raw": {"id": "duplicate"}}
            )
            invalid = HandballGame(
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

    def test_initialize_backfills_identities_for_existing_v111_games(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = HandballStorage(Path(temporary) / "handball")
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
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            pending = game(
                game_id="pending", status="NS", home_goals=None, away_goals=None
            )
            storage.upsert_games([pending])
            storage.create_shadow_pick(pick_payload(game_id="pending"))
            self.assertEqual(storage.open_pick_dates(), ["2026-07-20"])

    def test_settlement_is_idempotent_and_audited_append_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = HandballStorage(Path(temporary) / "handball")
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
            storage = HandballStorage(Path(temporary) / "handball")
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
                home_goals=None,
                away_goals=None,
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
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            past = game(
                game_id="feature-past",
                scheduled_at="2026-12-01T18:00:00+00:00",
            )
            target = game(
                game_id="feature-target",
                status="NS",
                home_goals=None,
                away_goals=None,
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
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            target = game(
                game_id="leak-target",
                status="NS",
                home_goals=None,
                away_goals=None,
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

    def test_market_consensus_closing_line_and_clv_are_immutable(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            target = game(
                game_id="clv-target",
                status="NS",
                home_goals=None,
                away_goals=None,
                scheduled_at="2026-12-10T18:00:00+00:00",
            )
            storage.upsert_games([target])

            early = build_no_vig_consensus(
                [
                    quote(
                        "one", "HOME", 2.00, game_id=target.game_id,
                        observed_at="2026-12-05T12:00:00+00:00",
                    ),
                    quote(
                        "one", "AWAY", 1.90, game_id=target.game_id,
                        observed_at="2026-12-05T12:00:00+00:00",
                    ),
                    quote(
                        "two", "HOME", 1.95, game_id=target.game_id,
                        observed_at="2026-12-05T12:00:00+00:00",
                    ),
                    quote(
                        "two", "AWAY", 1.95, game_id=target.game_id,
                        observed_at="2026-12-05T12:00:00+00:00",
                    ),
                ]
            )
            closing_source = build_no_vig_consensus(
                [
                    quote(
                        "one", "HOME", 1.80, game_id=target.game_id,
                        observed_at="2026-12-10T17:00:00+00:00",
                    ),
                    quote(
                        "one", "AWAY", 2.15, game_id=target.game_id,
                        observed_at="2026-12-10T17:00:00+00:00",
                    ),
                    quote(
                        "two", "HOME", 1.85, game_id=target.game_id,
                        observed_at="2026-12-10T17:00:00+00:00",
                    ),
                    quote(
                        "two", "AWAY", 2.10, game_id=target.game_id,
                        observed_at="2026-12-10T17:00:00+00:00",
                    ),
                ]
            )
            single_book_before_start = build_no_vig_consensus(
                [
                    quote(
                        "one", "HOME", 1.60, game_id=target.game_id,
                        observed_at="2026-12-10T17:30:00+00:00",
                    ),
                    quote(
                        "one", "AWAY", 2.50, game_id=target.game_id,
                        observed_at="2026-12-10T17:30:00+00:00",
                    ),
                ]
            )
            after_start = build_no_vig_consensus(
                [
                    quote(
                        "one", "HOME", 1.50, game_id=target.game_id,
                        observed_at="2026-12-10T19:00:00+00:00",
                    ),
                    quote(
                        "one", "AWAY", 2.80, game_id=target.game_id,
                        observed_at="2026-12-10T19:00:00+00:00",
                    ),
                ]
            )
            self.assertIsNotNone(early)
            self.assertIsNotNone(closing_source)
            self.assertIsNotNone(single_book_before_start)
            self.assertIsNotNone(after_start)
            _, early_key = storage.record_market_consensus(early.payload())
            _, closing_key = storage.record_market_consensus(
                closing_source.payload()
            )
            storage.record_market_consensus(single_book_before_start.payload())
            storage.record_market_consensus(after_start.payload())

            payload = pick_payload(game_id=target.game_id)
            payload["market_consensus_key"] = early_key
            payload["bookmaker_odds"] = 2.0
            self.assertTrue(storage.create_shadow_pick(payload))
            with storage.connect() as connection:
                link = connection.execute(
                    "SELECT * FROM pick_market_links"
                ).fetchone()
                self.assertEqual(link["consensus_key"], early_key)

            finished = game(
                game_id=target.game_id,
                scheduled_at=target.scheduled_at,
            )
            storage.upsert_games([finished])
            opened = storage.open_picks()[0]
            self.assertTrue(
                storage.close_pick(opened["pick_key"], "WON", 1.0, finished)
            )
            closed = storage.closed_picks()[0]
            closing = storage.capture_closing_market(finished)
            self.assertIsNotNone(closing)
            self.assertEqual(closing["source_consensus_key"], closing_key)
            self.assertEqual(
                closing["observed_at"], "2026-12-10T17:00:00+00:00"
            )
            self.assertTrue(storage.record_pick_clv(closed, closing))
            self.assertFalse(storage.record_pick_clv(closed, closing))
            coverage = storage.coverage_summary()
            self.assertEqual(coverage["closing_market_snapshots"], 1)
            self.assertEqual(coverage["clv_samples"], 1)
            self.assertEqual(coverage["market_linked_picks"], 1)
            with storage.connect() as connection:
                clv = connection.execute("SELECT * FROM pick_clv").fetchone()
                self.assertAlmostEqual(
                    clv["clv_price"],
                    2.0 / closing["best_home_odds"] - 1.0,
                    places=7,
                )
                with self.assertRaises(Exception):
                    connection.execute(
                        "UPDATE closing_market_snapshots SET lag_seconds=0"
                    )
                with self.assertRaises(Exception):
                    connection.execute("DELETE FROM pick_clv")

    def test_model_candidate_registry_is_idempotent_and_immutable(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            candidate = train_candidate(
                [training_game(index) for index in range(5)],
                minimum_rows=5,
            )
            inserted, candidate_id = storage.register_model_candidate(
                candidate.payload()
            )
            self.assertTrue(inserted)
            self.assertEqual(candidate_id, candidate.candidate_id)
            inserted_again, same_id = storage.register_model_candidate(
                candidate.payload()
            )
            self.assertFalse(inserted_again)
            self.assertEqual(same_id, candidate_id)
            coverage = storage.coverage_summary()
            self.assertEqual(coverage["model_training_datasets"], 1)
            self.assertEqual(coverage["model_candidates"], 1)
            self.assertEqual(coverage["reproducible_candidates"], 1)
            self.assertTrue(coverage["model_registry_integrity"])
            self.assertEqual(coverage["active_model_changes"], 0)
            self.assertEqual(storage.latest_candidate_dataset_rows(), 5)
            with storage.connect() as connection:
                with self.assertRaises(Exception):
                    connection.execute(
                        "UPDATE model_candidates SET registry_status='ACTIVE'"
                    )
                with self.assertRaises(Exception):
                    connection.execute("DELETE FROM model_training_datasets")

    def test_model_registry_rejects_tampered_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            candidate = train_candidate(
                [training_game(index) for index in range(4)],
                minimum_rows=4,
            ).payload()
            candidate["artifact"]["state"]["ratings"]["team-0"] = 9999.0
            artifact_json = json.dumps(
                candidate["artifact"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            candidate["artifact_sha256"] = hashlib.sha256(
                artifact_json.encode("utf-8")
            ).hexdigest()
            candidate["candidate_id"] = (
                f"handball_candidate_{candidate['artifact_sha256'][:24]}"
            )
            inserted, candidate_id = storage.register_model_candidate(candidate)
            self.assertFalse(inserted)
            self.assertFalse(candidate_id)
            self.assertEqual(storage.coverage_summary()["model_candidates"], 0)

    def test_v117_validation_registry_is_idempotent_and_immutable(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            candidate = train_candidate(
                [validation_game(index) for index in range(100)],
                minimum_rows=100,
            )
            inserted, candidate_id = storage.register_model_candidate(
                candidate.payload()
            )
            self.assertTrue(inserted)
            registered = storage.latest_model_candidate()
            self.assertEqual(registered["candidate_id"], candidate_id)
            report = validate_candidate(
                registered,
                settings=ValidationSettings(bootstrap_samples=100),
            )
            created, validation_id = storage.register_model_validation(report)
            self.assertTrue(created)
            self.assertEqual(validation_id, report["validation_id"])
            created_again, same_id = storage.register_model_validation(report)
            self.assertFalse(created_again)
            self.assertEqual(same_id, validation_id)
            coverage = storage.coverage_summary()
            self.assertEqual(coverage["model_validations"], 1)
            self.assertEqual(
                coverage["positive_walk_forward_validations"],
                int(report["status"] == "POSITIVE_VALIDATION_MANUAL_APPROVAL"),
            )
            self.assertTrue(coverage["validation_registry_integrity"])
            self.assertEqual(coverage["automatic_model_promotions"], 0)
            self.assertEqual(coverage["validation_active_model_changes"], 0)
            with storage.connect() as connection:
                with self.assertRaises(Exception):
                    connection.execute(
                        "UPDATE model_validations SET status='NO_ENOUGH_DATA'"
                    )
                with self.assertRaises(Exception):
                    connection.execute("DELETE FROM model_validations")

    def test_v117_migration_preserves_existing_v116_registry(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            candidate = train_candidate(
                [validation_game(index) for index in range(100)],
                minimum_rows=100,
            )
            inserted, candidate_id = storage.register_model_candidate(
                candidate.payload()
            )
            self.assertTrue(inserted)
            with storage.connect() as connection:
                connection.execute("DROP TABLE model_validations")
            storage.initialize()
            with storage.connect() as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM model_candidates WHERE candidate_id=?",
                        (candidate_id,),
                    ).fetchone()[0],
                    1,
                )
                self.assertIsNotNone(
                    connection.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name='model_validations'
                        """
                    ).fetchone()
                )

    def test_v10_migration_preserves_v117_candidate_and_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            candidate = train_candidate(
                [validation_game(index) for index in range(100)],
                minimum_rows=100,
            )
            inserted, candidate_id = storage.register_model_candidate(
                candidate.payload()
            )
            self.assertTrue(inserted)
            report = validate_candidate(
                storage.model_candidate(candidate_id),
                settings=ValidationSettings(bootstrap_samples=100),
            )
            storage.register_model_validation(report)
            with storage.connect() as connection:
                connection.execute("DROP TABLE model_lifecycle_events")
                connection.execute("DROP TABLE model_live_reports")
                connection.execute("DROP TABLE model_live_settlements")
                connection.execute("DROP TABLE model_live_predictions")
            storage.initialize()
            with storage.connect() as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM model_candidates WHERE candidate_id=?",
                        (candidate_id,),
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM model_validations"
                    ).fetchone()[0],
                    1,
                )
                tables = {
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name IN (
                            'model_live_predictions',
                            'model_live_settlements',
                            'model_live_reports',
                            'model_lifecycle_events'
                        )
                        """
                    ).fetchall()
                }
                self.assertEqual(
                    tables,
                    {
                        "model_live_predictions",
                        "model_live_settlements",
                        "model_live_reports",
                        "model_lifecycle_events",
                    },
                )

    def test_v116_migration_preserves_existing_v115_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            existing = game(
                game_id="v115-existing",
                status="NS",
                home_goals=None,
                away_goals=None,
            )
            storage.upsert_games([existing])
            storage.create_shadow_pick(pick_payload(game_id=existing.game_id))
            with storage.connect() as connection:
                connection.execute("DROP TABLE model_candidates")
                connection.execute("DROP TABLE model_training_datasets")
            storage.initialize()
            with storage.connect() as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM games WHERE game_id='v115-existing'"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM shadow_picks "
                        "WHERE game_id='v115-existing'"
                    ).fetchone()[0],
                    1,
                )
                tables = {
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name IN (
                            'model_training_datasets', 'model_candidates'
                        )
                        """
                    ).fetchall()
                }
                self.assertEqual(
                    tables, {"model_training_datasets", "model_candidates"}
                )

    def test_v115_migration_preserves_existing_v114_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            existing = game(
                game_id="v114-existing",
                status="NS",
                home_goals=None,
                away_goals=None,
            )
            storage.upsert_games([existing])
            storage.create_shadow_pick(pick_payload(game_id=existing.game_id))
            with storage.connect() as connection:
                connection.execute("DROP TABLE pick_market_links")
                connection.execute("DROP TABLE pick_clv")
                connection.execute("DROP TABLE closing_market_snapshots")
                connection.execute("DROP TABLE market_consensus_snapshots")
            storage.initialize()
            with storage.connect() as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM games WHERE game_id='v114-existing'"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM shadow_picks "
                        "WHERE game_id='v114-existing'"
                    ).fetchone()[0],
                    1,
                )
                tables = {
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name IN (
                            'market_consensus_snapshots',
                            'closing_market_snapshots',
                            'pick_clv',
                            'pick_market_links'
                        )
                        """
                    ).fetchall()
                }
                self.assertEqual(
                    tables,
                    {
                        "market_consensus_snapshots",
                        "closing_market_snapshots",
                        "pick_clv",
                        "pick_market_links",
                    },
                )

    def test_v114_migration_preserves_existing_v113_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = HandballStorage(Path(temporary) / "handball")
            storage.initialize()
            existing = game(
                game_id="v113-existing",
                status="NS",
                home_goals=None,
                away_goals=None,
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
                        "SELECT COUNT(*) FROM games WHERE game_id='v113-existing'"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM shadow_picks WHERE game_id='v113-existing'"
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


class HandballProviderTests(unittest.TestCase):
    def test_retry_is_bounded_and_observed(self):
        observed = []
        settings = load_handball_settings(require_key=False)
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
        client = ApiSportsHandballClient(
            settings, session=session, observer=observed.append
        )
        rows = client._get("games", {"date": "2026-07-23"})
        self.assertEqual(rows, [{"id": 1}])
        self.assertEqual(session.calls, 2)
        self.assertEqual(len(observed), 2)
        self.assertEqual(observed[0]["status"], "RETRY")
        self.assertEqual(observed[-1]["status"], "SUCCESS")
        self.assertEqual(observed[-1]["remaining"], 99)

    def test_regular_time_three_way_market_is_rejected_fail_closed(self):
        settings = load_handball_settings(require_key=False)
        session = _FakeSession([
            _FakeResponse(
                200,
                {
                    "errors": [],
                    "response": [{
                        "bookmakers": [{
                            "id": 1,
                            "name": "TestBook",
                            "bets": [{
                                "name": "Match Winner",
                                "values": [
                                    {"value": "Home", "odd": "1.80"},
                                    {"value": "Draw", "odd": "8.00"},
                                    {"value": "Away", "odd": "2.20"},
                                ],
                            }],
                        }],
                    }],
                },
            )
        ])
        client = ApiSportsHandballClient(settings, session=session)
        self.assertEqual(client.odds_for_game("game-1"), [])

    def test_two_way_no_draw_market_is_accepted(self):
        settings = load_handball_settings(require_key=False)
        session = _FakeSession([
            _FakeResponse(
                200,
                {
                    "errors": [],
                    "response": [{
                        "bookmakers": [{
                            "id": 1,
                            "name": "TestBook",
                            "bets": [{
                                "name": "Home/Away (incl. overtime)",
                                "values": [
                                    {"value": "Home", "odd": "1.80"},
                                    {"value": "Away", "odd": "2.20"},
                                ],
                            }],
                        }],
                    }],
                },
            )
        ])
        client = ApiSportsHandballClient(settings, session=session)
        quotes = client.odds_for_game("game-1")
        self.assertEqual({quote.outcome for quote in quotes}, {"HOME", "AWAY"})
        self.assertTrue(all(
            quote.market == "MATCH_WINNER_NO_DRAW" for quote in quotes
        ))


class HandballRuntimeSmokeTests(unittest.TestCase):
    def test_single_book_is_collected_but_cannot_create_pick_or_train(self):
        scheduled = (
            datetime.now(timezone.utc) + timedelta(days=1)
        ).isoformat(timespec="seconds")
        upcoming = game(
            game_id="handball-single-book",
            status="NS",
            home_goals=None,
            away_goals=None,
            scheduled_at=scheduled,
        )

        class FakeClient:
            def games_for_date(self, _day):
                return [upcoming]

            def odds_for_game(self, game_id):
                observed = datetime.now(timezone.utc).isoformat(timespec="seconds")
                return [
                    quote("only", "HOME", 1.80, game_id=game_id, observed_at=observed),
                    quote("only", "AWAY", 2.20, game_id=game_id, observed_at=observed),
                ]

        with tempfile.TemporaryDirectory() as root:
            storage = HandballStorage(Path(root) / "handball")
            storage.initialize()
            storage.set_state("initial_backfill_complete", "1")
            health = run_cycle(
                storage,
                FakeClient(),
                load_handball_settings(require_key=False),
            )
            self.assertEqual(health["single_book_shadow_observed"], 1)
            self.assertEqual(health["single_book_shadow_saved"], 1)
            self.assertEqual(health["single_book_training_admitted"], 0)
            self.assertEqual(health["single_book_picks_created"], 0)
            self.assertFalse(health["single_book_promotion_allowed"])
            self.assertEqual(health["picks_created"], 0)
            self.assertEqual(health["multi_book_consensus_saved"], 0)
            self.assertEqual(storage.coverage_summary()["market_consensus_snapshots"], 1)

    def test_full_collection_prediction_and_storage_cycle_is_isolated(self):
        scheduled = (
            datetime.now(timezone.utc) + timedelta(days=1)
        ).isoformat(timespec="seconds")
        upcoming = game(
            game_id="handball-runtime-1",
            status="NS",
            home_goals=None,
            away_goals=None,
            scheduled_at=scheduled,
        )

        class FakeClient:
            def games_for_date(self, _day):
                return [upcoming]

            def odds_for_game(self, game_id):
                observed = datetime.now(timezone.utc).isoformat(timespec="seconds")
                return [
                    quote("a", "HOME", 2.10, game_id=game_id, observed_at=observed),
                    quote("a", "AWAY", 1.80, game_id=game_id, observed_at=observed),
                    quote("b", "HOME", 2.05, game_id=game_id, observed_at=observed),
                    quote("b", "AWAY", 1.82, game_id=game_id, observed_at=observed),
                ]

        with tempfile.TemporaryDirectory() as root:
            storage = HandballStorage(Path(root) / "handball")
            storage.initialize()
            storage.set_state("initial_backfill_complete", "1")
            health = run_cycle(
                storage,
                FakeClient(),
                load_handball_settings(require_key=False),
            )
            self.assertEqual(health["status"], "HEALTHY")
            self.assertTrue(health["shadow_only"])
            self.assertFalse(health["real_execution_allowed"])
            self.assertFalse(health["football_data_modified"])
            self.assertFalse(health["volleyball_data_modified"])
            self.assertEqual(health["games_received"], 1)
            self.assertEqual(health["quotes_saved"], 4)
            self.assertGreaterEqual(health["picks_created"], 1)
            self.assertTrue(storage.db_path.exists())
            self.assertIn("handball", storage.db_path.parts)


if __name__ == "__main__":
    unittest.main()


