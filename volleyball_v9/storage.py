from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Iterable

from storage_paths import DATA_DIR

from .domain import OddsQuote, VolleyballGame, utc_now
from .features import parse_utc
from .identity import PROVIDER, identity_for, normalize_name, validate_game


def volleyball_data_dir(root: str | Path | None = None) -> Path:
    return Path(root) if root is not None else DATA_DIR / "volleyball"


class VolleyballStorage:
    def __init__(self, root: str | Path | None = None):
        self.root = volleyball_data_dir(root)
        self.db_path = self.root / "volleyball_shadow.sqlite3"

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS games (
                    game_id TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    scheduled_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    league_id TEXT,
                    league_name TEXT,
                    country TEXT,
                    season TEXT,
                    home_team_id TEXT NOT NULL,
                    home_team TEXT NOT NULL,
                    away_team_id TEXT NOT NULL,
                    away_team TEXT NOT NULL,
                    home_sets INTEGER,
                    away_sets INTEGER,
                    raw_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS odds_snapshots (
                    snapshot_key TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    game_id TEXT NOT NULL,
                    bookmaker_id TEXT,
                    bookmaker TEXT NOT NULL,
                    market TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    odds REAL NOT NULL,
                    observed_at TEXT NOT NULL,
                    FOREIGN KEY(game_id) REFERENCES games(game_id)
                );
                CREATE TABLE IF NOT EXISTS shadow_picks (
                    pick_key TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    created_at TEXT NOT NULL,
                    game_id TEXT NOT NULL,
                    league_name TEXT,
                    match_name TEXT NOT NULL,
                    market TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    bookmaker TEXT NOT NULL,
                    bookmaker_odds REAL NOT NULL,
                    model_probability REAL NOT NULL,
                    model_fair_odds REAL NOT NULL,
                    edge REAL NOT NULL,
                    confidence REAL NOT NULL,
                    model_version TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    result TEXT NOT NULL DEFAULT 'PENDING',
                    profit REAL NOT NULL DEFAULT 0,
                    settled_at TEXT,
                    raw_json TEXT NOT NULL,
                    FOREIGN KEY(game_id) REFERENCES games(game_id)
                );
                CREATE TABLE IF NOT EXISTS settlement_evidence (
                    evidence_key TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    pick_key TEXT NOT NULL,
                    game_id TEXT NOT NULL,
                    result TEXT NOT NULL,
                    home_sets INTEGER,
                    away_sets INTEGER,
                    provider TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    settled_at TEXT NOT NULL,
                    FOREIGN KEY(pick_key) REFERENCES shadow_picks(pick_key)
                );
                CREATE TABLE IF NOT EXISTS runtime_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS provider_calls (
                    call_id TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    endpoint TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    http_status INTEGER NOT NULL DEFAULT 0,
                    rows_received INTEGER NOT NULL DEFAULT 0,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    rate_limit_remaining INTEGER,
                    error_type TEXT,
                    error TEXT,
                    observed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_provider_calls_endpoint_time
                ON provider_calls(endpoint, observed_at);
                CREATE TABLE IF NOT EXISTS team_identities (
                    canonical_key TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    provider TEXT NOT NULL,
                    source_team_id TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    UNIQUE(provider, source_team_id)
                );
                CREATE TABLE IF NOT EXISTS league_identities (
                    canonical_key TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    provider TEXT NOT NULL,
                    source_league_id TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    country TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    UNIQUE(provider, source_league_id)
                );
                CREATE TABLE IF NOT EXISTS game_identities (
                    game_id TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    home_team_key TEXT NOT NULL,
                    away_team_key TEXT NOT NULL,
                    league_key TEXT NOT NULL,
                    game_fingerprint TEXT NOT NULL UNIQUE,
                    observed_at TEXT NOT NULL,
                    FOREIGN KEY(game_id) REFERENCES games(game_id),
                    FOREIGN KEY(home_team_key) REFERENCES team_identities(canonical_key),
                    FOREIGN KEY(away_team_key) REFERENCES team_identities(canonical_key),
                    FOREIGN KEY(league_key) REFERENCES league_identities(canonical_key)
                );
                CREATE TABLE IF NOT EXISTS identity_quarantine (
                    quarantine_key TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    game_id TEXT,
                    reason TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    observed_at TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS protect_identity_quarantine_update
                BEFORE UPDATE ON identity_quarantine
                BEGIN SELECT RAISE(ABORT, 'volleyball identity quarantine is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS protect_identity_quarantine_delete
                BEFORE DELETE ON identity_quarantine
                BEGIN SELECT RAISE(ABORT, 'volleyball identity quarantine is append-only'); END;
                CREATE TABLE IF NOT EXISTS settlement_audit (
                    audit_key TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    pick_key TEXT NOT NULL,
                    game_id TEXT NOT NULL,
                    stored_result TEXT NOT NULL,
                    recalculated_result TEXT NOT NULL,
                    audit_status TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    FOREIGN KEY(pick_key) REFERENCES shadow_picks(pick_key)
                );
                CREATE INDEX IF NOT EXISTS idx_settlement_audit_status
                ON settlement_audit(audit_status, observed_at);
                CREATE TRIGGER IF NOT EXISTS protect_settlement_audit_update
                BEFORE UPDATE ON settlement_audit
                BEGIN SELECT RAISE(ABORT, 'volleyball settlement audit is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS protect_settlement_audit_delete
                BEFORE DELETE ON settlement_audit
                BEGIN SELECT RAISE(ABORT, 'volleyball settlement audit is append-only'); END;
                CREATE TABLE IF NOT EXISTS feature_snapshots (
                    feature_key TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    game_id TEXT NOT NULL,
                    feature_schema TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    feature_cutoff_at TEXT NOT NULL,
                    scheduled_at TEXT NOT NULL,
                    home_team_id TEXT NOT NULL,
                    away_team_id TEXT NOT NULL,
                    home_rating REAL NOT NULL,
                    away_rating REAL NOT NULL,
                    home_matches INTEGER NOT NULL,
                    away_matches INTEGER NOT NULL,
                    home_probability REAL NOT NULL,
                    away_probability REAL NOT NULL,
                    confidence REAL NOT NULL,
                    source_games INTEGER NOT NULL,
                    source_max_scheduled_at TEXT,
                    source_max_observed_at TEXT,
                    leakage_status TEXT NOT NULL CHECK(leakage_status='PASS'),
                    payload_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(game_id) REFERENCES games(game_id)
                );
                CREATE INDEX IF NOT EXISTS idx_feature_snapshots_game_time
                ON feature_snapshots(game_id, observed_at);
                CREATE TABLE IF NOT EXISTS feature_quarantine (
                    quarantine_key TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    game_id TEXT,
                    reason TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    observed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pick_feature_links (
                    pick_key TEXT PRIMARY KEY,
                    feature_key TEXT NOT NULL,
                    linked_at TEXT NOT NULL,
                    FOREIGN KEY(pick_key) REFERENCES shadow_picks(pick_key),
                    FOREIGN KEY(feature_key) REFERENCES feature_snapshots(feature_key)
                );
                CREATE TABLE IF NOT EXISTS market_consensus_snapshots (
                    consensus_key TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    game_id TEXT NOT NULL,
                    market_schema TEXT NOT NULL,
                    market TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    bookmaker_count INTEGER NOT NULL,
                    home_probability REAL NOT NULL,
                    away_probability REAL NOT NULL,
                    home_fair_odds REAL NOT NULL,
                    away_fair_odds REAL NOT NULL,
                    best_home_odds REAL NOT NULL,
                    best_away_odds REAL NOT NULL,
                    average_overround REAL NOT NULL,
                    probability_dispersion REAL NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(game_id) REFERENCES games(game_id)
                );
                CREATE INDEX IF NOT EXISTS idx_market_consensus_game_time
                ON market_consensus_snapshots(game_id, market, observed_at);
                CREATE TABLE IF NOT EXISTS closing_market_snapshots (
                    closing_key TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    game_id TEXT NOT NULL,
                    market TEXT NOT NULL,
                    source_consensus_key TEXT NOT NULL,
                    scheduled_at TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    lag_seconds INTEGER NOT NULL,
                    bookmaker_count INTEGER NOT NULL,
                    home_probability REAL NOT NULL,
                    away_probability REAL NOT NULL,
                    home_fair_odds REAL NOT NULL,
                    away_fair_odds REAL NOT NULL,
                    best_home_odds REAL NOT NULL,
                    best_away_odds REAL NOT NULL,
                    captured_at TEXT NOT NULL,
                    UNIQUE(game_id, market),
                    FOREIGN KEY(game_id) REFERENCES games(game_id),
                    FOREIGN KEY(source_consensus_key)
                        REFERENCES market_consensus_snapshots(consensus_key)
                );
                CREATE TABLE IF NOT EXISTS pick_clv (
                    pick_key TEXT PRIMARY KEY,
                    closing_key TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    entry_odds REAL NOT NULL,
                    closing_best_odds REAL NOT NULL,
                    closing_fair_odds REAL NOT NULL,
                    clv_price REAL NOT NULL,
                    clv_fair REAL NOT NULL,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY(pick_key) REFERENCES shadow_picks(pick_key),
                    FOREIGN KEY(closing_key)
                        REFERENCES closing_market_snapshots(closing_key)
                );
                CREATE TABLE IF NOT EXISTS pick_market_links (
                    pick_key TEXT PRIMARY KEY,
                    consensus_key TEXT NOT NULL,
                    linked_at TEXT NOT NULL,
                    FOREIGN KEY(pick_key) REFERENCES shadow_picks(pick_key),
                    FOREIGN KEY(consensus_key)
                        REFERENCES market_consensus_snapshots(consensus_key)
                );
                CREATE TABLE IF NOT EXISTS model_training_datasets (
                    dataset_sha256 TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    training_schema TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    first_scheduled_at TEXT,
                    last_scheduled_at TEXT,
                    payload_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    registered_at TEXT NOT NULL,
                    CHECK(dataset_sha256=payload_sha256)
                );
                CREATE TABLE IF NOT EXISTS model_candidates (
                    candidate_id TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    dataset_sha256 TEXT NOT NULL,
                    candidate_schema TEXT NOT NULL,
                    algorithm TEXT NOT NULL,
                    hyperparameters_json TEXT NOT NULL,
                    artifact_sha256 TEXT NOT NULL UNIQUE,
                    artifact_json TEXT NOT NULL,
                    reproducible INTEGER NOT NULL CHECK(reproducible=1),
                    registry_status TEXT NOT NULL CHECK(registry_status='CANDIDATE_ONLY'),
                    active_model_modified INTEGER NOT NULL CHECK(active_model_modified=0),
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(dataset_sha256)
                        REFERENCES model_training_datasets(dataset_sha256)
                );
                CREATE INDEX IF NOT EXISTS idx_model_candidates_dataset
                ON model_candidates(dataset_sha256, created_at);
                CREATE TABLE IF NOT EXISTS model_validations (
                    validation_id TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    candidate_id TEXT NOT NULL,
                    validation_schema TEXT NOT NULL,
                    method TEXT NOT NULL CHECK(method='expanding_window_walk_forward'),
                    fold_count INTEGER NOT NULL,
                    oos_samples INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN (
                        'NO_ENOUGH_DATA',
                        'REJECTED_OR_REVIEW',
                        'POSITIVE_VALIDATION_MANUAL_APPROVAL'
                    )),
                    brier_improvement REAL NOT NULL,
                    log_loss_improvement REAL NOT NULL,
                    calibration_improvement REAL NOT NULL,
                    report_sha256 TEXT NOT NULL UNIQUE,
                    report_json TEXT NOT NULL,
                    automatic_promotion INTEGER NOT NULL CHECK(automatic_promotion=0),
                    active_model_modified INTEGER NOT NULL CHECK(active_model_modified=0),
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(candidate_id) REFERENCES model_candidates(candidate_id)
                );
                CREATE INDEX IF NOT EXISTS idx_model_validations_candidate
                ON model_validations(candidate_id, created_at);
                CREATE TABLE IF NOT EXISTS model_live_predictions (
                    prediction_key TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    candidate_id TEXT NOT NULL,
                    comparator_model_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('CHAMPION', 'CHALLENGER')),
                    game_id TEXT NOT NULL,
                    league_id TEXT,
                    scheduled_at TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    home_probability REAL NOT NULL CHECK(
                        home_probability>0 AND home_probability<1
                    ),
                    model_parameters_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(candidate_id, game_id, role),
                    FOREIGN KEY(candidate_id) REFERENCES model_candidates(candidate_id),
                    FOREIGN KEY(game_id) REFERENCES games(game_id)
                );
                CREATE INDEX IF NOT EXISTS idx_model_live_predictions_candidate
                ON model_live_predictions(candidate_id, role, scheduled_at);
                CREATE TABLE IF NOT EXISTS model_live_settlements (
                    prediction_key TEXT PRIMARY KEY,
                    target INTEGER NOT NULL CHECK(target IN (0, 1)),
                    brier_loss REAL NOT NULL,
                    log_loss REAL NOT NULL,
                    settled_at TEXT NOT NULL,
                    FOREIGN KEY(prediction_key)
                        REFERENCES model_live_predictions(prediction_key)
                );
                CREATE TABLE IF NOT EXISTS model_live_reports (
                    report_id TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    candidate_id TEXT NOT NULL,
                    report_schema TEXT NOT NULL,
                    settled_samples INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN (
                        'COLLECTING_LIVE_SHADOW',
                        'POSITIVE_LIVE_SHADOW',
                        'NEGATIVE_LIVE_SHADOW'
                    )),
                    positive INTEGER NOT NULL CHECK(positive IN (0, 1)),
                    drift_status TEXT NOT NULL,
                    report_sha256 TEXT NOT NULL UNIQUE,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(candidate_id) REFERENCES model_candidates(candidate_id)
                );
                CREATE INDEX IF NOT EXISTS idx_model_live_reports_candidate
                ON model_live_reports(candidate_id, settled_samples, created_at);
                CREATE TABLE IF NOT EXISTS model_lifecycle_events (
                    event_id TEXT PRIMARY KEY,
                    sport TEXT NOT NULL DEFAULT 'volleyball' CHECK(sport='volleyball'),
                    candidate_id TEXT NOT NULL,
                    event_type TEXT NOT NULL CHECK(event_type IN (
                        'PROMOTED_SHADOW',
                        'ROLLED_BACK_SHADOW'
                    )),
                    previous_model_id TEXT NOT NULL,
                    evidence_report_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(candidate_id) REFERENCES model_candidates(candidate_id)
                );
                CREATE INDEX IF NOT EXISTS idx_model_lifecycle_events_time
                ON model_lifecycle_events(created_at, event_id);
                CREATE TRIGGER IF NOT EXISTS protect_feature_snapshots_update
                BEFORE UPDATE ON feature_snapshots
                BEGIN SELECT RAISE(ABORT, 'volleyball feature snapshot is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS protect_feature_snapshots_delete
                BEFORE DELETE ON feature_snapshots
                BEGIN SELECT RAISE(ABORT, 'volleyball feature snapshot is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS protect_feature_quarantine_update
                BEFORE UPDATE ON feature_quarantine
                BEGIN SELECT RAISE(ABORT, 'volleyball feature quarantine is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS protect_feature_quarantine_delete
                BEFORE DELETE ON feature_quarantine
                BEGIN SELECT RAISE(ABORT, 'volleyball feature quarantine is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS protect_pick_feature_links_update
                BEFORE UPDATE ON pick_feature_links
                BEGIN SELECT RAISE(ABORT, 'volleyball pick feature link is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_pick_feature_links_delete
                BEFORE DELETE ON pick_feature_links
                BEGIN SELECT RAISE(ABORT, 'volleyball pick feature link is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_market_consensus_update
                BEFORE UPDATE ON market_consensus_snapshots
                BEGIN SELECT RAISE(ABORT, 'volleyball market consensus is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS protect_market_consensus_delete
                BEFORE DELETE ON market_consensus_snapshots
                BEGIN SELECT RAISE(ABORT, 'volleyball market consensus is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS protect_closing_market_update
                BEFORE UPDATE ON closing_market_snapshots
                BEGIN SELECT RAISE(ABORT, 'volleyball closing market is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_closing_market_delete
                BEFORE DELETE ON closing_market_snapshots
                BEGIN SELECT RAISE(ABORT, 'volleyball closing market is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_pick_clv_update
                BEFORE UPDATE ON pick_clv
                BEGIN SELECT RAISE(ABORT, 'volleyball pick CLV is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_pick_clv_delete
                BEFORE DELETE ON pick_clv
                BEGIN SELECT RAISE(ABORT, 'volleyball pick CLV is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_pick_market_links_update
                BEFORE UPDATE ON pick_market_links
                BEGIN SELECT RAISE(ABORT, 'volleyball pick market link is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_pick_market_links_delete
                BEFORE DELETE ON pick_market_links
                BEGIN SELECT RAISE(ABORT, 'volleyball pick market link is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_model_training_datasets_update
                BEFORE UPDATE ON model_training_datasets
                BEGIN SELECT RAISE(ABORT, 'volleyball training dataset is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_model_training_datasets_delete
                BEFORE DELETE ON model_training_datasets
                BEGIN SELECT RAISE(ABORT, 'volleyball training dataset is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_model_candidates_update
                BEFORE UPDATE ON model_candidates
                BEGIN SELECT RAISE(ABORT, 'volleyball candidate is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_model_candidates_delete
                BEFORE DELETE ON model_candidates
                BEGIN SELECT RAISE(ABORT, 'volleyball candidate is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_model_validations_update
                BEFORE UPDATE ON model_validations
                BEGIN SELECT RAISE(ABORT, 'volleyball validation is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_model_validations_delete
                BEFORE DELETE ON model_validations
                BEGIN SELECT RAISE(ABORT, 'volleyball validation is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_model_live_predictions_update
                BEFORE UPDATE ON model_live_predictions
                BEGIN SELECT RAISE(ABORT, 'volleyball live prediction is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_model_live_predictions_delete
                BEFORE DELETE ON model_live_predictions
                BEGIN SELECT RAISE(ABORT, 'volleyball live prediction is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_model_live_settlements_update
                BEFORE UPDATE ON model_live_settlements
                BEGIN SELECT RAISE(ABORT, 'volleyball live settlement is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_model_live_settlements_delete
                BEFORE DELETE ON model_live_settlements
                BEGIN SELECT RAISE(ABORT, 'volleyball live settlement is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_model_live_reports_update
                BEFORE UPDATE ON model_live_reports
                BEGIN SELECT RAISE(ABORT, 'volleyball live report is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_model_live_reports_delete
                BEFORE DELETE ON model_live_reports
                BEGIN SELECT RAISE(ABORT, 'volleyball live report is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_model_lifecycle_events_update
                BEFORE UPDATE ON model_lifecycle_events
                BEGIN SELECT RAISE(ABORT, 'volleyball lifecycle event is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_model_lifecycle_events_delete
                BEFORE DELETE ON model_lifecycle_events
                BEGIN SELECT RAISE(ABORT, 'volleyball lifecycle event is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_settled_pick_update
                BEFORE UPDATE ON shadow_picks
                WHEN OLD.status='CLOSED'
                BEGIN SELECT RAISE(ABORT, 'closed volleyball pick is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_settled_pick_delete
                BEFORE DELETE ON shadow_picks
                WHEN OLD.status='CLOSED'
                BEGIN SELECT RAISE(ABORT, 'closed volleyball pick is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS protect_evidence_update
                BEFORE UPDATE ON settlement_evidence
                BEGIN SELECT RAISE(ABORT, 'volleyball evidence is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS protect_evidence_delete
                BEFORE DELETE ON settlement_evidence
                BEGIN SELECT RAISE(ABORT, 'volleyball evidence is append-only'); END;
                """
            )
            missing_identities = connection.execute(
                """
                SELECT COUNT(*) FROM games g
                LEFT JOIN game_identities i ON i.game_id=g.game_id
                WHERE i.game_id IS NULL
                """
            ).fetchone()[0]
        if missing_identities:
            self.upsert_games(self.load_games())

    def upsert_games(self, games: Iterable[VolleyballGame]) -> int:
        count = 0
        with self.connect() as connection:
            for game in games:
                reasons = validate_game(game)
                if reasons:
                    self._quarantine(connection, game, ",".join(reasons))
                    continue
                identity = identity_for(game)
                duplicate = connection.execute(
                    """
                    SELECT game_id FROM game_identities
                    WHERE game_fingerprint=? AND game_id<>?
                    """,
                    (identity.fingerprint, game.game_id),
                ).fetchone()
                if duplicate is not None:
                    self._quarantine(
                        connection,
                        game,
                        f"duplicate_fingerprint_existing_game:{duplicate['game_id']}",
                    )
                    continue
                connection.execute(
                    """
                    INSERT INTO games (
                        game_id, scheduled_at, status, league_id, league_name, country,
                        season, home_team_id, home_team, away_team_id, away_team,
                        home_sets, away_sets, raw_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(game_id) DO UPDATE SET
                        scheduled_at=excluded.scheduled_at, status=excluded.status,
                        league_id=excluded.league_id, league_name=excluded.league_name,
                        country=excluded.country, season=excluded.season,
                        home_team_id=excluded.home_team_id, home_team=excluded.home_team,
                        away_team_id=excluded.away_team_id, away_team=excluded.away_team,
                        home_sets=excluded.home_sets, away_sets=excluded.away_sets,
                        raw_json=excluded.raw_json, updated_at=excluded.updated_at
                    """,
                    (
                        game.game_id, game.scheduled_at, game.status, game.league_id,
                        game.league_name, game.country, game.season, game.home_team_id,
                        game.home_team, game.away_team_id, game.away_team,
                        game.home_sets, game.away_sets,
                        json.dumps(game.raw, ensure_ascii=False, sort_keys=True), utc_now(),
                    ),
                )
                now = utc_now()
                for canonical_key, source_id, display_name in (
                    (identity.team_home_key, game.home_team_id, game.home_team),
                    (identity.team_away_key, game.away_team_id, game.away_team),
                ):
                    connection.execute(
                        """
                        INSERT INTO team_identities (
                            canonical_key, provider, source_team_id, normalized_name,
                            display_name, first_seen_at, last_seen_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(provider, source_team_id) DO UPDATE SET
                            normalized_name=excluded.normalized_name,
                            display_name=excluded.display_name,
                            last_seen_at=excluded.last_seen_at
                        """,
                        (
                            canonical_key, PROVIDER, source_id,
                            normalize_name(display_name), display_name, now, now,
                        ),
                    )
                connection.execute(
                    """
                    INSERT INTO league_identities (
                        canonical_key, provider, source_league_id, normalized_name,
                        display_name, country, first_seen_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(provider, source_league_id) DO UPDATE SET
                        normalized_name=excluded.normalized_name,
                        display_name=excluded.display_name,
                        country=excluded.country,
                        last_seen_at=excluded.last_seen_at
                    """,
                    (
                        identity.league_key, PROVIDER, game.league_id,
                        normalize_name(game.league_name), game.league_name,
                        game.country, now, now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO game_identities (
                        game_id, home_team_key, away_team_key, league_key,
                        game_fingerprint, observed_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(game_id) DO UPDATE SET
                        home_team_key=excluded.home_team_key,
                        away_team_key=excluded.away_team_key,
                        league_key=excluded.league_key,
                        game_fingerprint=excluded.game_fingerprint,
                        observed_at=excluded.observed_at
                    """,
                    (
                        game.game_id, identity.team_home_key, identity.team_away_key,
                        identity.league_key, identity.fingerprint, now,
                    ),
                )
                count += 1
        return count

    @staticmethod
    def _quarantine(
        connection: sqlite3.Connection, game: VolleyballGame, reason: str
    ) -> None:
        payload = json.dumps(game.raw, ensure_ascii=False, sort_keys=True)
        payload_sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        quarantine_key = hashlib.sha256(
            f"{game.game_id}|{reason}|{payload_sha}".encode("utf-8")
        ).hexdigest()
        connection.execute(
            """
            INSERT OR IGNORE INTO identity_quarantine (
                quarantine_key, game_id, reason, payload_sha256,
                payload_json, observed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                quarantine_key, game.game_id or None, reason, payload_sha,
                payload, utc_now(),
            ),
        )

    def load_games(self, *, finished_only: bool = False) -> list[VolleyballGame]:
        query = "SELECT * FROM games"
        with self.connect() as connection:
            rows = connection.execute(query).fetchall()
        games = []
        for row in rows:
            game = VolleyballGame(
                game_id=row["game_id"], scheduled_at=row["scheduled_at"],
                status=row["status"], league_id=row["league_id"] or "",
                league_name=row["league_name"] or "UNKNOWN", country=row["country"] or "",
                season=row["season"] or "", home_team_id=row["home_team_id"],
                home_team=row["home_team"], away_team_id=row["away_team_id"],
                away_team=row["away_team"], home_sets=row["home_sets"],
                away_sets=row["away_sets"], raw=json.loads(row["raw_json"]),
            )
            if not finished_only or game.finished:
                games.append(game)
        return games

    def save_odds(self, quotes: Iterable[OddsQuote]) -> int:
        count = 0
        with self.connect() as connection:
            for quote in quotes:
                raw_key = "|".join(
                    [quote.game_id, quote.bookmaker_id, quote.market, quote.outcome, quote.observed_at]
                )
                key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO odds_snapshots (
                        snapshot_key, game_id, bookmaker_id, bookmaker, market,
                        outcome, odds, observed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key, quote.game_id, quote.bookmaker_id, quote.bookmaker,
                        quote.market, quote.outcome, quote.odds, quote.observed_at,
                    ),
                )
                count += int(cursor.rowcount == 1)
        return count

    def record_provider_call(self, payload: dict) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO provider_calls (
                    call_id, endpoint, params_json, attempt, status, http_status,
                    rows_received, duration_ms, rate_limit_remaining, error_type,
                    error, observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["call_id"], payload["endpoint"], payload["params_json"],
                    int(payload.get("attempt", 1)), payload["status"],
                    int(payload.get("http_status", 0)), int(payload.get("rows", 0)),
                    int(payload.get("duration_ms", 0)), payload.get("remaining"),
                    payload.get("error_type"), payload.get("error"), utc_now(),
                ),
            )

    def coverage_summary(self) -> dict:
        with self.connect() as connection:
            games = connection.execute("SELECT COUNT(*) FROM games").fetchone()[0]
            finished = connection.execute(
                "SELECT COUNT(*) FROM games WHERE home_sets IS NOT NULL AND away_sets IS NOT NULL"
            ).fetchone()[0]
            games_with_odds = connection.execute(
                "SELECT COUNT(DISTINCT game_id) FROM odds_snapshots"
            ).fetchone()[0]
            quotes = connection.execute(
                "SELECT COUNT(*) FROM odds_snapshots"
            ).fetchone()[0]
            calls = connection.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN status='SUCCESS' THEN 1 ELSE 0 END) AS ok,
                       SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) AS failed
                FROM provider_calls
                """
            ).fetchone()
            quarantined = connection.execute(
                "SELECT COUNT(*) FROM identity_quarantine"
            ).fetchone()[0]
            identities = connection.execute(
                "SELECT COUNT(*) FROM game_identities"
            ).fetchone()[0]
            settlement_audits = connection.execute(
                "SELECT COUNT(*) FROM settlement_audit"
            ).fetchone()[0]
            settlement_mismatches = connection.execute(
                "SELECT COUNT(*) FROM settlement_audit WHERE audit_status='MISMATCH'"
            ).fetchone()[0]
            feature_snapshots = connection.execute(
                "SELECT COUNT(*) FROM feature_snapshots"
            ).fetchone()[0]
            feature_quarantined = connection.execute(
                "SELECT COUNT(*) FROM feature_quarantine"
            ).fetchone()[0]
            feature_linked_picks = connection.execute(
                "SELECT COUNT(*) FROM pick_feature_links"
            ).fetchone()[0]
            market_consensus = connection.execute(
                "SELECT COUNT(*) FROM market_consensus_snapshots"
            ).fetchone()[0]
            multi_book_consensus = connection.execute(
                """
                SELECT COUNT(*) FROM market_consensus_snapshots
                WHERE bookmaker_count>=2
                """
            ).fetchone()[0]
            closing_markets = connection.execute(
                "SELECT COUNT(*) FROM closing_market_snapshots"
            ).fetchone()[0]
            clv = connection.execute(
                """
                SELECT COUNT(*) AS samples, AVG(clv_price) AS average_price,
                       AVG(clv_fair) AS average_fair
                FROM pick_clv
                """
            ).fetchone()
            market_linked_picks = connection.execute(
                "SELECT COUNT(*) FROM pick_market_links"
            ).fetchone()[0]
            training_datasets = connection.execute(
                "SELECT COUNT(*) FROM model_training_datasets"
            ).fetchone()[0]
            candidates = connection.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN reproducible=1 THEN 1 ELSE 0 END) AS verified,
                       SUM(CASE WHEN active_model_modified<>0 THEN 1 ELSE 0 END) AS active_changes
                FROM model_candidates
                """
            ).fetchone()
            candidate_rows = connection.execute(
                "SELECT artifact_sha256, artifact_json FROM model_candidates"
            ).fetchall()
            validations = connection.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN status='POSITIVE_VALIDATION_MANUAL_APPROVAL'
                                THEN 1 ELSE 0 END) AS positive,
                       SUM(CASE WHEN automatic_promotion<>0 THEN 1 ELSE 0 END)
                           AS automatic_promotions,
                       SUM(CASE WHEN active_model_modified<>0 THEN 1 ELSE 0 END)
                           AS active_changes
                FROM model_validations
                """
            ).fetchone()
            validation_rows = connection.execute(
                "SELECT report_sha256, report_json FROM model_validations"
            ).fetchall()
            live_predictions = connection.execute(
                "SELECT COUNT(*) FROM model_live_predictions"
            ).fetchone()[0]
            live_settlements = connection.execute(
                "SELECT COUNT(*) FROM model_live_settlements"
            ).fetchone()[0]
            live_reports = connection.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN positive=1 THEN 1 ELSE 0 END) AS positive
                FROM model_live_reports
                """
            ).fetchone()
            lifecycle = connection.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN event_type='PROMOTED_SHADOW'
                                THEN 1 ELSE 0 END) AS promotions,
                       SUM(CASE WHEN event_type='ROLLED_BACK_SHADOW'
                                THEN 1 ELSE 0 END) AS rollbacks
                FROM model_lifecycle_events
                """
            ).fetchone()
            live_integrity_rows = connection.execute(
                """
                SELECT payload_sha256 AS expected, payload_json AS payload
                FROM model_live_predictions
                UNION ALL
                SELECT report_sha256 AS expected, report_json AS payload
                FROM model_live_reports
                UNION ALL
                SELECT payload_sha256 AS expected, payload_json AS payload
                FROM model_lifecycle_events
                """
            ).fetchall()
        registry_integrity = all(
            hashlib.sha256(str(row["artifact_json"]).encode("utf-8")).hexdigest()
            == str(row["artifact_sha256"])
            for row in candidate_rows
        )
        validation_integrity = all(
            hashlib.sha256(str(row["report_json"]).encode("utf-8")).hexdigest()
            == str(row["report_sha256"])
            for row in validation_rows
        )
        live_registry_integrity = all(
            hashlib.sha256(str(row["payload"]).encode("utf-8")).hexdigest()
            == str(row["expected"])
            for row in live_integrity_rows
        )
        eligible = max(0, int(games) - int(finished))
        return {
            "games_total": int(games),
            "games_finished": int(finished),
            "games_upcoming": eligible,
            "games_with_odds": int(games_with_odds),
            "odds_quotes": int(quotes),
            "upcoming_odds_coverage": round(
                min(1.0, int(games_with_odds) / eligible), 6
            ) if eligible else 0.0,
            "provider_calls": int(calls["total"] or 0),
            "provider_success": int(calls["ok"] or 0),
            "provider_failed": int(calls["failed"] or 0),
            "identity_records": int(identities),
            "identity_quarantined": int(quarantined),
            "identity_acceptance_rate": round(
                int(identities) / (int(identities) + int(quarantined)), 6
            ) if int(identities) + int(quarantined) else 0.0,
            "settlement_audits": int(settlement_audits),
            "settlement_mismatches": int(settlement_mismatches),
            "feature_snapshots": int(feature_snapshots),
            "feature_quarantined": int(feature_quarantined),
            "feature_linked_picks": int(feature_linked_picks),
            "feature_leakage_rate": round(
                int(feature_quarantined)
                / (int(feature_snapshots) + int(feature_quarantined)),
                6,
            ) if int(feature_snapshots) + int(feature_quarantined) else 0.0,
            "market_consensus_snapshots": int(market_consensus),
            "multi_book_consensus_snapshots": int(multi_book_consensus),
            "closing_market_snapshots": int(closing_markets),
            "clv_samples": int(clv["samples"] or 0),
            "average_clv_price": round(float(clv["average_price"] or 0.0), 8),
            "average_clv_fair": round(float(clv["average_fair"] or 0.0), 8),
            "market_linked_picks": int(market_linked_picks),
            "model_training_datasets": int(training_datasets),
            "model_candidates": int(candidates["total"] or 0),
            "reproducible_candidates": int(candidates["verified"] or 0),
            "model_registry_integrity": registry_integrity,
            "active_model_changes": int(candidates["active_changes"] or 0),
            "model_validations": int(validations["total"] or 0),
            "positive_walk_forward_validations": int(
                validations["positive"] or 0
            ),
            "validation_registry_integrity": validation_integrity,
            "automatic_model_promotions": int(
                validations["automatic_promotions"] or 0
            ),
            "validation_active_model_changes": int(
                validations["active_changes"] or 0
            ),
            "live_shadow_predictions": int(live_predictions),
            "live_shadow_settlements": int(live_settlements),
            "live_shadow_reports": int(live_reports["total"] or 0),
            "positive_live_shadow_reports": int(live_reports["positive"] or 0),
            "shadow_model_promotions": int(lifecycle["promotions"] or 0),
            "shadow_model_rollbacks": int(lifecycle["rollbacks"] or 0),
            "model_lifecycle_events": int(lifecycle["total"] or 0),
            "live_registry_integrity": live_registry_integrity,
        }

    def register_model_candidate(self, payload: dict) -> tuple[bool, str]:
        from .training import (
            CANDIDATE_SCHEMA_VERSION,
            CandidateBundle,
            TRAINING_SCHEMA_VERSION,
            canonical_json,
            sha256_text,
            verify_candidate,
        )

        dataset = payload.get("dataset_document")
        artifact = payload.get("artifact")
        if not isinstance(dataset, dict) or not isinstance(artifact, dict):
            return False, ""
        dataset_json = canonical_json(dataset)
        artifact_json = canonical_json(artifact)
        dataset_sha = sha256_text(dataset_json)
        artifact_sha = sha256_text(artifact_json)
        candidate_id = f"volleyball_candidate_{artifact_sha[:24]}"
        verification_bundle = CandidateBundle(
            status="CANDIDATE_READY",
            dataset_sha256=dataset_sha,
            dataset_rows=int(dataset.get("row_count", -1)),
            minimum_rows=int(payload.get("minimum_rows", 1)),
            dataset_document=dataset,
            artifact=artifact,
            artifact_sha256=artifact_sha,
            candidate_id=candidate_id,
            reproducible=True,
        )
        if (
            dataset_sha != payload.get("dataset_sha256")
            or artifact_sha != payload.get("artifact_sha256")
            or candidate_id != payload.get("candidate_id")
            or dataset.get("schema_version") != TRAINING_SCHEMA_VERSION
            or artifact.get("schema_version") != CANDIDATE_SCHEMA_VERSION
            or artifact.get("registry_status") != "CANDIDATE_ONLY"
            or artifact.get("active_model_modified") is not False
            or artifact.get("dataset", {}).get("sha256") != dataset_sha
            or int(dataset.get("row_count", -1)) != len(dataset.get("rows", []))
            or payload.get("reproducible") is not True
            or not verify_candidate(verification_bundle)
        ):
            return False, ""
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO model_training_datasets (
                    dataset_sha256, training_schema, row_count,
                    first_scheduled_at, last_scheduled_at, payload_sha256,
                    payload_json, registered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset_sha, TRAINING_SCHEMA_VERSION, dataset["row_count"],
                    dataset.get("first_scheduled_at"),
                    dataset.get("last_scheduled_at"), dataset_sha,
                    dataset_json, utc_now(),
                ),
            )
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO model_candidates (
                    candidate_id, dataset_sha256, candidate_schema, algorithm,
                    hyperparameters_json, artifact_sha256, artifact_json,
                    reproducible, registry_status, active_model_modified,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'CANDIDATE_ONLY', 0, ?)
                """,
                (
                    candidate_id, dataset_sha, CANDIDATE_SCHEMA_VERSION,
                    artifact["algorithm"],
                    canonical_json(artifact["hyperparameters"]),
                    artifact_sha, artifact_json, utc_now(),
                ),
            )
        return cursor.rowcount == 1, candidate_id

    def latest_candidate_dataset_rows(self) -> int:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT d.row_count
                FROM model_candidates c
                JOIN model_training_datasets d
                  ON d.dataset_sha256=c.dataset_sha256
                ORDER BY c.created_at DESC, c.candidate_id DESC
                LIMIT 1
                """
            ).fetchone()
        return 0 if row is None else int(row["row_count"])

    def latest_model_candidate(self) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT c.*, d.payload_json AS dataset_json
                FROM model_candidates c
                JOIN model_training_datasets d
                  ON d.dataset_sha256=c.dataset_sha256
                WHERE c.reproducible=1
                  AND c.registry_status='CANDIDATE_ONLY'
                  AND c.active_model_modified=0
                ORDER BY c.created_at DESC, c.candidate_id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        try:
            dataset = json.loads(str(row["dataset_json"]))
            artifact = json.loads(str(row["artifact_json"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return {
            "candidate_id": str(row["candidate_id"]),
            "dataset_sha256": str(row["dataset_sha256"]),
            "artifact_sha256": str(row["artifact_sha256"]),
            "dataset_document": dataset,
            "artifact": artifact,
            "reproducible": bool(row["reproducible"]),
            "active_model_modified": bool(row["active_model_modified"]),
        }

    def register_model_validation(self, payload: dict) -> tuple[bool, str]:
        from .training import canonical_json, sha256_text
        from .validation import VALIDATION_METHOD, VALIDATION_SCHEMA_VERSION

        validation_id = str(payload.get("validation_id", ""))
        candidate_id = str(payload.get("candidate_id", ""))
        report_sha = str(payload.get("report_sha256", ""))
        report = {
            key: value
            for key, value in payload.items()
            if key not in {"validation_id", "report_sha256", "validation_created"}
        }
        report_json = canonical_json(report)
        expected_sha = sha256_text(report_json)
        expected_id = f"volleyball_validation_{expected_sha[:24]}"
        allowed_statuses = {
            "NO_ENOUGH_DATA",
            "REJECTED_OR_REVIEW",
            "POSITIVE_VALIDATION_MANUAL_APPROVAL",
        }
        if (
            validation_id != expected_id
            or report_sha != expected_sha
            or report.get("validation_schema") != VALIDATION_SCHEMA_VERSION
            or report.get("method") != VALIDATION_METHOD
            or report.get("status") not in allowed_statuses
            or report.get("automatic_promotion") is not False
            or report.get("active_model_modified") is not False
            or report.get("manual_approval_required") is not True
            or report.get("real_execution_allowed") is not False
        ):
            return False, ""
        with self.connect() as connection:
            candidate = connection.execute(
                """
                SELECT candidate_id FROM model_candidates
                WHERE candidate_id=? AND reproducible=1
                  AND registry_status='CANDIDATE_ONLY'
                  AND active_model_modified=0
                """,
                (candidate_id,),
            ).fetchone()
            if candidate is None:
                return False, ""
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO model_validations (
                    validation_id, candidate_id, validation_schema, method,
                    fold_count, oos_samples, status, brier_improvement,
                    log_loss_improvement, calibration_improvement,
                    report_sha256, report_json, automatic_promotion,
                    active_model_modified, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
                """,
                (
                    validation_id,
                    candidate_id,
                    VALIDATION_SCHEMA_VERSION,
                    VALIDATION_METHOD,
                    int(report.get("folds", 0)),
                    int(report.get("oos_samples", 0)),
                    str(report["status"]),
                    float(report.get("brier_improvement", 0.0)),
                    float(report.get("log_loss_improvement", 0.0)),
                    float(report.get("calibration_improvement", 0.0)),
                    report_sha,
                    report_json,
                    utc_now(),
                ),
            )
        return cursor.rowcount == 1, validation_id

    def validation_for_candidate(self, candidate_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT report_json FROM model_validations
                WHERE candidate_id=?
                ORDER BY created_at DESC, validation_id DESC
                LIMIT 1
                """,
                (str(candidate_id),),
            ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(str(row["report_json"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    def model_candidate(self, candidate_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT c.*, d.payload_json AS dataset_json
                FROM model_candidates c
                JOIN model_training_datasets d
                  ON d.dataset_sha256=c.dataset_sha256
                WHERE c.candidate_id=? AND c.reproducible=1
                  AND c.registry_status='CANDIDATE_ONLY'
                  AND c.active_model_modified=0
                """,
                (str(candidate_id),),
            ).fetchone()
        if row is None:
            return None
        try:
            return {
                "candidate_id": str(row["candidate_id"]),
                "dataset_sha256": str(row["dataset_sha256"]),
                "artifact_sha256": str(row["artifact_sha256"]),
                "dataset_document": json.loads(str(row["dataset_json"])),
                "artifact": json.loads(str(row["artifact_json"])),
                "reproducible": bool(row["reproducible"]),
                "active_model_modified": bool(row["active_model_modified"]),
            }
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    def record_live_prediction(
        self,
        *,
        candidate_id: str,
        comparator_model_id: str,
        role: str,
        game: VolleyballGame,
        observed_at: str,
        home_probability: float,
        model_parameters: dict,
    ) -> tuple[bool, str]:
        from .training import canonical_json, sha256_text

        selected_role = str(role).upper()
        probability = float(home_probability)
        if (
            selected_role not in {"CHAMPION", "CHALLENGER"}
            or not (0.0 < probability < 1.0)
            or parse_utc(observed_at) >= parse_utc(game.scheduled_at)
        ):
            return False, ""
        payload = {
            "candidate_id": str(candidate_id),
            "comparator_model_id": str(comparator_model_id),
            "role": selected_role,
            "game_id": str(game.game_id),
            "league_id": str(game.league_id),
            "scheduled_at": str(game.scheduled_at),
            "observed_at": str(observed_at),
            "home_probability": round(probability, 10),
            "model_parameters": dict(model_parameters),
            "shadow_only": True,
            "real_execution_allowed": False,
        }
        payload_json = canonical_json(payload)
        payload_sha = sha256_text(payload_json)
        prediction_key = f"volleyball_live_prediction_{payload_sha[:24]}"
        with self.connect() as connection:
            candidate = connection.execute(
                "SELECT candidate_id FROM model_candidates WHERE candidate_id=?",
                (str(candidate_id),),
            ).fetchone()
            if candidate is None:
                return False, ""
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO model_live_predictions (
                    prediction_key, candidate_id, comparator_model_id, role,
                    game_id, league_id, scheduled_at, observed_at,
                    home_probability, model_parameters_json,
                    payload_sha256, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prediction_key,
                    str(candidate_id),
                    str(comparator_model_id),
                    selected_role,
                    str(game.game_id),
                    str(game.league_id),
                    str(game.scheduled_at),
                    str(observed_at),
                    round(probability, 10),
                    canonical_json(dict(model_parameters)),
                    payload_sha,
                    payload_json,
                ),
            )
        return cursor.rowcount == 1, prediction_key

    def settle_live_predictions(
        self,
        games: Iterable[VolleyballGame],
    ) -> int:
        game_index = {
            str(game.game_id): game
            for game in games
            if game.finished
            and game.home_sets is not None
            and game.away_sets is not None
            and game.home_sets != game.away_sets
        }
        if not game_index:
            return 0
        inserted = 0
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT p.prediction_key, p.game_id, p.home_probability
                FROM model_live_predictions p
                LEFT JOIN model_live_settlements s
                  ON s.prediction_key=p.prediction_key
                WHERE s.prediction_key IS NULL
                """
            ).fetchall()
            for row in rows:
                game = game_index.get(str(row["game_id"]))
                if game is None:
                    continue
                target = 1 if int(game.home_sets) > int(game.away_sets) else 0
                probability = min(
                    1.0 - 1e-12,
                    max(1e-12, float(row["home_probability"])),
                )
                brier = (probability - target) ** 2
                log_loss = -(
                    target * math.log(probability)
                    + (1 - target) * math.log(1.0 - probability)
                )
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO model_live_settlements (
                        prediction_key, target, brier_loss, log_loss, settled_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(row["prediction_key"]),
                        target,
                        brier,
                        log_loss,
                        utc_now(),
                    ),
                )
                inserted += int(cursor.rowcount == 1)
        return inserted

    def paired_live_rows(self, candidate_id: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT c.game_id, c.league_id, c.scheduled_at,
                       c.home_probability AS champion_probability,
                       ch.home_probability AS challenger_probability,
                       sc.target,
                       sc.brier_loss AS champion_brier,
                       sch.brier_loss AS challenger_brier,
                       sc.log_loss AS champion_log_loss,
                       sch.log_loss AS challenger_log_loss
                FROM model_live_predictions c
                JOIN model_live_predictions ch
                  ON ch.candidate_id=c.candidate_id
                 AND ch.game_id=c.game_id
                 AND ch.role='CHALLENGER'
                JOIN model_live_settlements sc
                  ON sc.prediction_key=c.prediction_key
                JOIN model_live_settlements sch
                  ON sch.prediction_key=ch.prediction_key
                WHERE c.candidate_id=? AND c.role='CHAMPION'
                ORDER BY c.scheduled_at, c.game_id
                """,
                (str(candidate_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def register_live_report(self, payload: dict) -> tuple[bool, str]:
        from .training import canonical_json, sha256_text
        from .governor import LIVE_REPORT_SCHEMA_VERSION

        report = {
            key: value
            for key, value in payload.items()
            if key not in {"report_id", "report_sha256", "report_created"}
        }
        report_json = canonical_json(report)
        report_sha = sha256_text(report_json)
        report_id = f"volleyball_live_report_{report_sha[:24]}"
        if (
            payload.get("report_id") != report_id
            or payload.get("report_sha256") != report_sha
            or report.get("report_schema") != LIVE_REPORT_SCHEMA_VERSION
            or report.get("status")
            not in {
                "COLLECTING_LIVE_SHADOW",
                "POSITIVE_LIVE_SHADOW",
                "NEGATIVE_LIVE_SHADOW",
            }
            or report.get("real_execution_allowed") is not False
        ):
            return False, ""
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO model_live_reports (
                    report_id, candidate_id, report_schema, settled_samples,
                    status, positive, drift_status, report_sha256,
                    report_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    str(report["candidate_id"]),
                    LIVE_REPORT_SCHEMA_VERSION,
                    int(report.get("settled_samples", 0)),
                    str(report["status"]),
                    int(bool(report.get("positive", False))),
                    str(report.get("drift_status", "UNKNOWN")),
                    report_sha,
                    report_json,
                    utc_now(),
                ),
            )
        return cursor.rowcount == 1, report_id

    def live_report_counts(self, candidate_id: str) -> dict:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN positive=1 THEN 1 ELSE 0 END) AS positive,
                       SUM(CASE WHEN positive=0
                                 AND status='NEGATIVE_LIVE_SHADOW'
                                THEN 1 ELSE 0 END) AS negative
                FROM model_live_reports WHERE candidate_id=?
                """,
                (str(candidate_id),),
            ).fetchone()
        return {
            "total": int(row["total"] or 0),
            "positive": int(row["positive"] or 0),
            "negative": int(row["negative"] or 0),
        }

    def latest_live_report_samples(self, candidate_id: str) -> int:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT settled_samples FROM model_live_reports
                WHERE candidate_id=?
                ORDER BY settled_samples DESC, created_at DESC
                LIMIT 1
                """,
                (str(candidate_id),),
            ).fetchone()
        return 0 if row is None else int(row["settled_samples"])

    def recent_live_report_statuses(
        self,
        candidate_id: str,
        limit: int,
    ) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT status FROM model_live_reports
                WHERE candidate_id=?
                ORDER BY settled_samples DESC, rowid DESC
                LIMIT ?
                """,
                (str(candidate_id), max(1, int(limit))),
            ).fetchall()
        return [str(row["status"]) for row in rows]

    def record_lifecycle_event(
        self,
        *,
        candidate_id: str,
        event_type: str,
        previous_model_id: str,
        evidence_report_id: str,
        reason: str,
    ) -> tuple[bool, str]:
        from .training import canonical_json, sha256_text

        selected_type = str(event_type).upper()
        if selected_type not in {"PROMOTED_SHADOW", "ROLLED_BACK_SHADOW"}:
            return False, ""
        payload = {
            "candidate_id": str(candidate_id),
            "event_type": selected_type,
            "previous_model_id": str(previous_model_id or "BASELINE"),
            "evidence_report_id": str(evidence_report_id),
            "reason": str(reason),
            "shadow_only": True,
            "real_execution_allowed": False,
            "football_model_modified": False,
        }
        payload_json = canonical_json(payload)
        payload_sha = sha256_text(payload_json)
        event_id = f"volleyball_lifecycle_{payload_sha[:24]}"
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO model_lifecycle_events (
                    event_id, candidate_id, event_type, previous_model_id,
                    evidence_report_id, reason, payload_sha256, payload_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    str(candidate_id),
                    selected_type,
                    str(previous_model_id or "BASELINE"),
                    str(evidence_report_id),
                    str(reason),
                    payload_sha,
                    payload_json,
                    utc_now(),
                ),
            )
        return cursor.rowcount == 1, event_id

    def active_shadow_model_id(self) -> str:
        active = "BASELINE"
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT candidate_id, event_type, previous_model_id
                FROM model_lifecycle_events
                ORDER BY rowid
                """
            ).fetchall()
        for row in rows:
            if row["event_type"] == "PROMOTED_SHADOW":
                active = str(row["candidate_id"])
            elif row["event_type"] == "ROLLED_BACK_SHADOW":
                active = str(row["previous_model_id"] or "BASELINE")
        return active

    def comparator_model_id(self, candidate_id: str) -> str:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT previous_model_id
                FROM model_lifecycle_events
                WHERE candidate_id=? AND event_type='PROMOTED_SHADOW'
                ORDER BY rowid DESC LIMIT 1
                """,
                (str(candidate_id),),
            ).fetchone()
        return "BASELINE" if row is None else str(
            row["previous_model_id"] or "BASELINE"
        )

    def active_shadow_model(self) -> dict | None:
        candidate_id = self.active_shadow_model_id()
        if candidate_id == "BASELINE":
            return None
        return self.model_candidate(candidate_id)

    def point_in_time_training_set(
        self, target: VolleyballGame, observed_at: str
    ) -> tuple[list[VolleyballGame], dict]:
        observed = parse_utc(observed_at)
        scheduled = parse_utc(target.scheduled_at)
        if observed >= scheduled:
            return [], {
                "source_games": 0,
                "source_max_scheduled_at": None,
                "source_max_observed_at": None,
                "rejection_reason": "feature_observed_at_not_before_match",
            }
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM games
                WHERE home_sets IS NOT NULL AND away_sets IS NOT NULL
                ORDER BY scheduled_at, game_id
                """
            ).fetchall()
        eligible: list[VolleyballGame] = []
        source_scheduled: list[str] = []
        source_observed: list[str] = []
        for row in rows:
            try:
                game_time = parse_utc(str(row["scheduled_at"]))
                source_time = parse_utc(str(row["updated_at"]))
            except ValueError:
                continue
            if game_time >= observed or source_time > observed:
                continue
            eligible.append(
                VolleyballGame(
                    game_id=row["game_id"], scheduled_at=row["scheduled_at"],
                    status=row["status"], league_id=row["league_id"] or "",
                    league_name=row["league_name"] or "UNKNOWN",
                    country=row["country"] or "", season=row["season"] or "",
                    home_team_id=row["home_team_id"], home_team=row["home_team"],
                    away_team_id=row["away_team_id"], away_team=row["away_team"],
                    home_sets=row["home_sets"], away_sets=row["away_sets"],
                    raw=json.loads(row["raw_json"]),
                )
            )
            source_scheduled.append(str(row["scheduled_at"]))
            source_observed.append(str(row["updated_at"]))
        return eligible, {
            "source_games": len(eligible),
            "source_max_scheduled_at": max(source_scheduled) if source_scheduled else None,
            "source_max_observed_at": max(source_observed) if source_observed else None,
            "rejection_reason": None,
        }

    @staticmethod
    def _feature_leakage_reasons(payload: dict) -> list[str]:
        reasons: list[str] = []
        try:
            observed = parse_utc(str(payload["observed_at"]))
            cutoff = parse_utc(str(payload["feature_cutoff_at"]))
            scheduled = parse_utc(str(payload["scheduled_at"]))
        except (KeyError, TypeError, ValueError):
            return ["invalid_feature_timestamps"]
        if observed >= scheduled:
            reasons.append("feature_observed_at_not_before_match")
        if cutoff > observed:
            reasons.append("feature_cutoff_after_observation")
        if cutoff >= scheduled:
            reasons.append("feature_cutoff_not_before_match")
        source_games = int(payload.get("source_games", 0) or 0)
        source_scheduled = payload.get("source_max_scheduled_at")
        source_observed = payload.get("source_max_observed_at")
        if source_games:
            if not source_scheduled or not source_observed:
                reasons.append("missing_source_provenance")
            else:
                try:
                    if parse_utc(str(source_scheduled)) >= cutoff:
                        reasons.append("source_game_not_before_feature_cutoff")
                    if parse_utc(str(source_observed)) > observed:
                        reasons.append("source_observed_after_feature")
                except ValueError:
                    reasons.append("invalid_source_timestamps")
        probability = float(payload.get("home_probability", -1))
        away_probability = float(payload.get("away_probability", -1))
        if not (0.0 < probability < 1.0 and 0.0 < away_probability < 1.0):
            reasons.append("invalid_probability")
        if abs((probability + away_probability) - 1.0) > 0.000001:
            reasons.append("probabilities_not_normalized")
        return sorted(set(reasons))

    def record_feature_snapshot(self, payload: dict) -> tuple[bool, str, str]:
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        payload_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        reasons = self._feature_leakage_reasons(payload)
        if reasons:
            reason = ",".join(reasons)
            self.record_feature_rejection(
                game_id=str(payload.get("game_id") or ""),
                observed_at=str(payload.get("observed_at") or utc_now()),
                reason=reason,
                details=payload,
            )
            return False, "", "BLOCKED"
        raw_key = "|".join(
            [
                str(payload["game_id"]), str(payload["feature_schema"]),
                str(payload["model_version"]), str(payload["observed_at"]),
                payload_hash,
            ]
        )
        feature_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO feature_snapshots (
                    feature_key, game_id, feature_schema, model_version,
                    observed_at, feature_cutoff_at, scheduled_at,
                    home_team_id, away_team_id, home_rating, away_rating,
                    home_matches, away_matches, home_probability,
                    away_probability, confidence, source_games,
                    source_max_scheduled_at, source_max_observed_at,
                    leakage_status, payload_sha256, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feature_key, payload["game_id"], payload["feature_schema"],
                    payload["model_version"], payload["observed_at"],
                    payload["feature_cutoff_at"], payload["scheduled_at"],
                    payload["home_team_id"], payload["away_team_id"],
                    payload["home_rating"], payload["away_rating"],
                    payload["home_matches"], payload["away_matches"],
                    payload["home_probability"], payload["away_probability"],
                    payload["confidence"], payload["source_games"],
                    payload.get("source_max_scheduled_at"),
                    payload.get("source_max_observed_at"), "PASS",
                    payload_hash, serialized,
                ),
            )
        return cursor.rowcount == 1, feature_key, "PASS"

    def record_feature_rejection(
        self,
        *,
        game_id: str,
        observed_at: str,
        reason: str,
        details: dict | None = None,
    ) -> bool:
        payload = {
            "game_id": game_id,
            "feature_observed_at": observed_at,
            "reason": reason,
            "details": details or {},
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        payload_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        quarantine_key = hashlib.sha256(
            f"{game_id}|{reason}|{payload_hash}".encode("utf-8")
        ).hexdigest()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO feature_quarantine (
                    quarantine_key, game_id, reason, payload_sha256,
                    payload_json, observed_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    quarantine_key, game_id or None, reason, payload_hash,
                    serialized, utc_now(),
                ),
            )
        return cursor.rowcount == 1

    def record_market_consensus(self, payload: dict) -> tuple[bool, str]:
        home_probability = float(payload["home_probability"])
        away_probability = float(payload["away_probability"])
        if not (
            0.0 < home_probability < 1.0
            and 0.0 < away_probability < 1.0
            and abs(home_probability + away_probability - 1.0) <= 0.000001
        ):
            return False, ""
        if int(payload["bookmaker_count"]) < 1:
            return False, ""
        if min(
            float(payload["best_home_odds"]),
            float(payload["best_away_odds"]),
            float(payload["home_fair_odds"]),
            float(payload["away_fair_odds"]),
        ) <= 1.0:
            return False, ""
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        payload_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        raw_key = "|".join(
            [
                str(payload["game_id"]), str(payload["market"]),
                str(payload["observed_at"]), str(payload["market_schema"]),
                payload_hash,
            ]
        )
        consensus_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO market_consensus_snapshots (
                    consensus_key, game_id, market_schema, market, observed_at,
                    bookmaker_count, home_probability, away_probability,
                    home_fair_odds, away_fair_odds, best_home_odds,
                    best_away_odds, average_overround,
                    probability_dispersion, payload_sha256, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    consensus_key, payload["game_id"], payload["market_schema"],
                    payload["market"], payload["observed_at"],
                    payload["bookmaker_count"], home_probability,
                    away_probability, payload["home_fair_odds"],
                    payload["away_fair_odds"], payload["best_home_odds"],
                    payload["best_away_odds"], payload["average_overround"],
                    payload["probability_dispersion"], payload_hash, serialized,
                ),
            )
        return cursor.rowcount == 1, consensus_key

    def capture_closing_market(
        self, game: VolleyballGame, market: str = "MATCH_WINNER"
    ) -> sqlite3.Row | None:
        with self.connect() as connection:
            source = connection.execute(
                """
                SELECT * FROM market_consensus_snapshots
                WHERE game_id=? AND market=? AND observed_at<?
                ORDER BY observed_at DESC, consensus_key DESC
                LIMIT 1
                """,
                (game.game_id, market, game.scheduled_at),
            ).fetchone()
            if source is None:
                return None
            lag_seconds = max(
                0,
                int(
                    (
                        parse_utc(game.scheduled_at)
                        - parse_utc(str(source["observed_at"]))
                    ).total_seconds()
                ),
            )
            closing_key = hashlib.sha256(
                (
                    f"{game.game_id}|{market}|{source['consensus_key']}|"
                    f"{game.scheduled_at}"
                ).encode("utf-8")
            ).hexdigest()
            connection.execute(
                """
                INSERT OR IGNORE INTO closing_market_snapshots (
                    closing_key, game_id, market, source_consensus_key,
                    scheduled_at, observed_at, lag_seconds, bookmaker_count,
                    home_probability, away_probability, home_fair_odds,
                    away_fair_odds, best_home_odds, best_away_odds, captured_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    closing_key, game.game_id, market,
                    source["consensus_key"], game.scheduled_at,
                    source["observed_at"], lag_seconds,
                    source["bookmaker_count"], source["home_probability"],
                    source["away_probability"], source["home_fair_odds"],
                    source["away_fair_odds"], source["best_home_odds"],
                    source["best_away_odds"], utc_now(),
                ),
            )
            return connection.execute(
                """
                SELECT * FROM closing_market_snapshots
                WHERE game_id=? AND market=?
                """,
                (game.game_id, market),
            ).fetchone()

    def record_pick_clv(
        self, pick: sqlite3.Row, closing: sqlite3.Row
    ) -> bool:
        outcome = str(pick["outcome"]).upper()
        if outcome == "HOME":
            closing_best = float(closing["best_home_odds"])
            closing_fair = float(closing["home_fair_odds"])
        elif outcome == "AWAY":
            closing_best = float(closing["best_away_odds"])
            closing_fair = float(closing["away_fair_odds"])
        else:
            return False
        entry_odds = float(pick["bookmaker_odds"])
        if min(entry_odds, closing_best, closing_fair) <= 1.0:
            return False
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO pick_clv (
                    pick_key, closing_key, outcome, entry_odds,
                    closing_best_odds, closing_fair_odds,
                    clv_price, clv_fair, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pick["pick_key"], closing["closing_key"], outcome,
                    entry_odds, closing_best, closing_fair,
                    round(entry_odds / closing_best - 1.0, 8),
                    round(entry_odds / closing_fair - 1.0, 8),
                    utc_now(),
                ),
            )
        return cursor.rowcount == 1

    def odds_refresh_due(
        self,
        game_id: str,
        refresh_hours: int,
        *,
        scheduled_at: str | None = None,
    ) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT MAX(observed_at) AS latest
                FROM odds_snapshots WHERE game_id=?
                """,
                (str(game_id),),
            ).fetchone()
        latest = None if row is None else row["latest"]
        if not latest:
            return True
        from datetime import datetime, timedelta, timezone
        try:
            observed = datetime.fromisoformat(str(latest).replace("Z", "+00:00"))
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            effective_hours = int(refresh_hours)
            if scheduled_at:
                starts_in = parse_utc(scheduled_at) - datetime.now(timezone.utc)
                if timedelta(0) < starts_in <= timedelta(hours=6):
                    effective_hours = 1
                elif timedelta(0) < starts_in <= timedelta(hours=24):
                    effective_hours = min(effective_hours, 3)
            return datetime.now(timezone.utc) - observed >= timedelta(
                hours=effective_hours
            )
        except ValueError:
            return True

    def create_shadow_pick(self, payload: dict) -> bool:
        raw_key = "|".join(
            [
                str(payload["game_id"]), str(payload["market"]),
                str(payload["outcome"]), str(payload["bookmaker"]),
                str(payload["model_version"]),
            ]
        )
        key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO shadow_picks (
                    pick_key, created_at, game_id, league_name, match_name, market,
                    outcome, bookmaker, bookmaker_odds, model_probability,
                    model_fair_odds, edge, confidence, model_version, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key, utc_now(), payload["game_id"], payload.get("league_name", ""),
                    payload["match_name"], payload["market"], payload["outcome"],
                    payload["bookmaker"], payload["bookmaker_odds"],
                    payload["model_probability"], payload["model_fair_odds"],
                    payload["edge"], payload["confidence"], payload["model_version"],
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                ),
            )
            if cursor.rowcount == 1 and payload.get("feature_key"):
                connection.execute(
                    """
                    INSERT INTO pick_feature_links (pick_key, feature_key, linked_at)
                    VALUES (?, ?, ?)
                    """,
                    (key, payload["feature_key"], utc_now()),
                )
            if cursor.rowcount == 1 and payload.get("market_consensus_key"):
                connection.execute(
                    """
                    INSERT INTO pick_market_links (
                        pick_key, consensus_key, linked_at
                    ) VALUES (?, ?, ?)
                    """,
                    (key, payload["market_consensus_key"], utc_now()),
                )
            return cursor.rowcount == 1

    def open_picks(self) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM shadow_picks WHERE status='OPEN' ORDER BY created_at"
            ).fetchall()

    def closed_picks(self) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM shadow_picks WHERE status='CLOSED' ORDER BY settled_at"
            ).fetchall()

    def open_pick_dates(self) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT substr(g.scheduled_at, 1, 10) AS game_date
                FROM shadow_picks p
                JOIN games g ON g.game_id=p.game_id
                WHERE p.status='OPEN' AND length(g.scheduled_at)>=10
                ORDER BY game_date
                """
            ).fetchall()
        return [str(row["game_date"]) for row in rows if row["game_date"]]

    def close_pick(
        self, pick_key: str, result: str, profit: float, game: VolleyballGame
    ) -> bool:
        payload = json.dumps(game.raw, ensure_ascii=False, sort_keys=True)
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        evidence_key = hashlib.sha256(
            f"{pick_key}|{game.game_id}|{result}|{payload_hash}".encode("utf-8")
        ).hexdigest()
        settled_at = utc_now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE shadow_picks SET status='CLOSED', result=?, profit=?, settled_at=?
                WHERE pick_key=? AND status='OPEN'
                """,
                (result, profit, settled_at, pick_key),
            )
            if cursor.rowcount != 1:
                return False
            connection.execute(
                """
                INSERT OR IGNORE INTO settlement_evidence (
                    evidence_key, pick_key, game_id, result, home_sets, away_sets,
                    provider, payload_sha256, payload_json, settled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_key, pick_key, game.game_id, result, game.home_sets,
                    game.away_sets, "api-sports-volleyball", payload_hash, payload,
                    settled_at,
                ),
            )
        return True

    def record_settlement_audit(
        self, pick: sqlite3.Row, game: VolleyballGame, recalculated_result: str
    ) -> tuple[bool, str]:
        stored_result = str(pick["result"])
        audit_status = (
            "CONSISTENT" if stored_result == recalculated_result else "MISMATCH"
        )
        payload = json.dumps(game.raw, ensure_ascii=False, sort_keys=True)
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        audit_key = hashlib.sha256(
            (
                f"{pick['pick_key']}|{stored_result}|{recalculated_result}|"
                f"{payload_hash}"
            ).encode("utf-8")
        ).hexdigest()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO settlement_audit (
                    audit_key, pick_key, game_id, stored_result,
                    recalculated_result, audit_status, provider,
                    payload_sha256, payload_json, observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_key, pick["pick_key"], game.game_id, stored_result,
                    recalculated_result, audit_status, "api-sports-volleyball",
                    payload_hash, payload, utc_now(),
                ),
            )
        return cursor.rowcount == 1, audit_status

    def state(self, key: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT value FROM runtime_state WHERE key=?", (key,)
            ).fetchone()
        return None if row is None else str(row["value"])

    def set_state(self, key: str, value: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO runtime_state(key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, value, utc_now()),
            )
