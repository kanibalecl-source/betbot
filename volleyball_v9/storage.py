from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Iterable

from storage_paths import DATA_DIR

from .domain import OddsQuote, VolleyballGame, utc_now
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
        }

    def odds_refresh_due(self, game_id: str, refresh_hours: int) -> bool:
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
            return datetime.now(timezone.utc) - observed >= timedelta(
                hours=refresh_hours
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
