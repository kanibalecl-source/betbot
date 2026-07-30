from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from storage_paths import DATA_DIR

from .domain import BasketballGame, BasketballOddsQuote, utc_now
from .settlement import settle_game


class BasketballStorage:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(
            db_path
            or DATA_DIR / "basketball" / "basketball_shadow.sqlite3"
        )

    @contextmanager
    def _connect(self):
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
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS basketball_games (
                    game_id TEXT PRIMARY KEY,
                    scheduled_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    league_id TEXT NOT NULL,
                    league_name TEXT NOT NULL,
                    country TEXT NOT NULL,
                    season TEXT NOT NULL,
                    home_team_id TEXT NOT NULL,
                    home_team TEXT NOT NULL,
                    away_team_id TEXT NOT NULL,
                    away_team TEXT NOT NULL,
                    home_score INTEGER,
                    away_score INTEGER,
                    overtime INTEGER NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS basketball_odds (
                    quote_key TEXT PRIMARY KEY,
                    game_id TEXT NOT NULL,
                    bookmaker_id TEXT NOT NULL,
                    bookmaker TEXT NOT NULL,
                    market TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    line REAL,
                    odds REAL NOT NULL,
                    observed_at TEXT NOT NULL,
                    admitted_training INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(game_id) REFERENCES basketball_games(game_id)
                );
                CREATE INDEX IF NOT EXISTS idx_basketball_odds_game
                    ON basketball_odds(game_id, observed_at);
                CREATE TABLE IF NOT EXISTS basketball_settlements (
                    game_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    winner TEXT NOT NULL,
                    home_score INTEGER,
                    away_score INTEGER,
                    total_points INTEGER,
                    margin INTEGER,
                    overtime INTEGER NOT NULL DEFAULT 0,
                    quality_status TEXT NOT NULL,
                    settled_at TEXT NOT NULL,
                    audited_at TEXT NOT NULL,
                    FOREIGN KEY(game_id) REFERENCES basketball_games(game_id)
                );
                CREATE TABLE IF NOT EXISTS basketball_provider_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    status_code INTEGER,
                    rows_received INTEGER NOT NULL DEFAULT 0,
                    success INTEGER NOT NULL,
                    error_type TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS basketball_quarantine (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(game_id, reason)
                );
                CREATE TABLE IF NOT EXISTS basketball_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def validate_game(game: BasketballGame) -> tuple[bool, str]:
        if not game.game_id:
            return False, "MISSING_GAME_ID"
        if not game.scheduled_at:
            return False, "MISSING_SCHEDULE"
        if not game.home_team_id or not game.away_team_id:
            return False, "MISSING_TEAM_ID"
        if not game.home_team or not game.away_team:
            return False, "MISSING_TEAM_NAME"
        if game.home_team_id == game.away_team_id:
            return False, "IDENTICAL_TEAMS"
        if game.home_score is not None and not 0 <= game.home_score <= 300:
            return False, "INVALID_HOME_SCORE"
        if game.away_score is not None and not 0 <= game.away_score <= 300:
            return False, "INVALID_AWAY_SCORE"
        return True, "PASS"

    def quarantine(self, game: BasketballGame, reason: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO basketball_quarantine
                    (game_id, reason, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    game.game_id or "UNKNOWN",
                    reason,
                    json.dumps(game.raw, ensure_ascii=False, default=str),
                    utc_now(),
                ),
            )

    def upsert_games(self, games: Iterable[BasketballGame]) -> dict[str, int]:
        admitted = 0
        quarantined = 0
        now = utc_now()
        with self._connect() as connection:
            for game in games:
                valid, reason = self.validate_game(game)
                if not valid:
                    quarantined += 1
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO basketball_quarantine
                            (game_id, reason, payload_json, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            game.game_id or "UNKNOWN", reason,
                            json.dumps(
                                game.raw, ensure_ascii=False, default=str
                            ),
                            now,
                        ),
                    )
                    continue
                connection.execute(
                    """
                    INSERT INTO basketball_games VALUES (
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )
                    ON CONFLICT(game_id) DO UPDATE SET
                        scheduled_at=excluded.scheduled_at,
                        status=excluded.status,
                        league_id=excluded.league_id,
                        league_name=excluded.league_name,
                        country=excluded.country,
                        season=excluded.season,
                        home_team_id=excluded.home_team_id,
                        home_team=excluded.home_team,
                        away_team_id=excluded.away_team_id,
                        away_team=excluded.away_team,
                        home_score=excluded.home_score,
                        away_score=excluded.away_score,
                        overtime=excluded.overtime,
                        raw_json=excluded.raw_json,
                        updated_at=excluded.updated_at
                    """,
                    (
                        game.game_id, game.scheduled_at, game.status,
                        game.league_id, game.league_name, game.country,
                        game.season, game.home_team_id, game.home_team,
                        game.away_team_id, game.away_team, game.home_score,
                        game.away_score, int(game.overtime),
                        json.dumps(
                            game.raw, ensure_ascii=False, sort_keys=True
                        ),
                        now, now,
                    ),
                )
                admitted += 1
        return {"admitted": admitted, "quarantined": quarantined}

    def load_games(self) -> list[BasketballGame]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM basketball_games ORDER BY scheduled_at"
            ).fetchall()
        return [
            BasketballGame(
                game_id=row["game_id"],
                scheduled_at=row["scheduled_at"],
                status=row["status"],
                league_id=row["league_id"],
                league_name=row["league_name"],
                country=row["country"],
                season=row["season"],
                home_team_id=row["home_team_id"],
                home_team=row["home_team"],
                away_team_id=row["away_team_id"],
                away_team=row["away_team"],
                home_score=row["home_score"],
                away_score=row["away_score"],
                overtime=bool(row["overtime"]),
                raw=json.loads(row["raw_json"]),
            )
            for row in rows
        ]

    def save_odds(self, quotes: Iterable[BasketballOddsQuote]) -> int:
        rows = []
        for quote in quotes:
            if not quote.game_id or not quote.bookmaker or quote.odds <= 1.0:
                continue
            raw = "|".join(
                [
                    quote.game_id, quote.bookmaker_id, quote.market,
                    quote.outcome, str(quote.line), f"{quote.odds:.8f}",
                    quote.observed_at,
                ]
            )
            rows.append(
                (
                    hashlib.sha256(raw.encode()).hexdigest()[:40],
                    quote.game_id, quote.bookmaker_id, quote.bookmaker,
                    quote.market, quote.outcome, quote.line, quote.odds,
                    quote.observed_at,
                )
            )
        if not rows:
            return 0
        with self._connect() as connection:
            before = connection.total_changes
            connection.executemany(
                """
                INSERT OR IGNORE INTO basketball_odds (
                    quote_key, game_id, bookmaker_id, bookmaker, market,
                    outcome, line, odds, observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            return connection.total_changes - before

    def odds_refresh_due(
        self,
        game_id: str,
        refresh_hours: int,
        *,
        empty_refresh_hours: int,
    ) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT MAX(observed_at) FROM basketball_odds WHERE game_id=?",
                (game_id,),
            ).fetchone()
            state = connection.execute(
                "SELECT value FROM basketball_state WHERE key=?",
                (f"odds_attempt:{game_id}",),
            ).fetchone()
        raw = row[0] if row and row[0] else (state[0] if state else "")
        if not raw:
            return True
        try:
            observed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            hours = refresh_hours if row and row[0] else empty_refresh_hours
            return datetime.now(timezone.utc) - observed >= timedelta(hours=hours)
        except ValueError:
            return True

    def mark_odds_attempt(self, game_id: str) -> None:
        self.set_state(f"odds_attempt:{game_id}", utc_now())

    def settle_finished_games(self) -> dict[str, int]:
        counts = {"settled": 0, "void": 0, "review": 0}
        now = utc_now()
        with self._connect() as connection:
            games = connection.execute(
                """
                SELECT * FROM basketball_games
                WHERE status IN (
                    'FT','AOT','AP','AW','ENDED','CLOSED','FINISHED',
                    'CANC','ABD','INTR','POST','CANCELLED','ABANDONED',
                    'POSTPONED','SUSPENDED'
                )
                """
            ).fetchall()
            for row in games:
                game = BasketballGame(
                    game_id=row["game_id"],
                    scheduled_at=row["scheduled_at"],
                    status=row["status"],
                    league_id=row["league_id"],
                    league_name=row["league_name"],
                    country=row["country"],
                    season=row["season"],
                    home_team_id=row["home_team_id"],
                    home_team=row["home_team"],
                    away_team_id=row["away_team_id"],
                    away_team=row["away_team"],
                    home_score=row["home_score"],
                    away_score=row["away_score"],
                    overtime=bool(row["overtime"]),
                    raw=json.loads(row["raw_json"]),
                )
                result = settle_game(game)
                status = str(result["status"])
                if status == "PENDING":
                    continue
                quality = "PASS" if status == "SETTLED" else "EXCLUDED"
                previous = connection.execute(
                    """
                    SELECT status, home_score, away_score
                    FROM basketball_settlements WHERE game_id=?
                    """,
                    (game.game_id,),
                ).fetchone()
                connection.execute(
                    """
                    INSERT INTO basketball_settlements VALUES (
                        ?,?,?,?,?,?,?,?,?,?,?
                    )
                    ON CONFLICT(game_id) DO UPDATE SET
                        status=excluded.status,
                        winner=excluded.winner,
                        home_score=excluded.home_score,
                        away_score=excluded.away_score,
                        total_points=excluded.total_points,
                        margin=excluded.margin,
                        overtime=excluded.overtime,
                        quality_status=excluded.quality_status,
                        audited_at=excluded.audited_at
                    """,
                    (
                        game.game_id, status, str(result.get("winner", "")),
                        game.home_score, game.away_score,
                        result.get("total_points"), result.get("margin"),
                        int(bool(result.get("overtime", False))), quality,
                        now, now,
                    ),
                )
                changed = (
                    previous is None
                    or str(previous["status"]) != status
                    or previous["home_score"] != game.home_score
                    or previous["away_score"] != game.away_score
                )
                if changed:
                    key = status.lower()
                    counts[key if key in counts else "review"] += 1
        return counts

    def record_provider_call(
        self,
        provider: str,
        endpoint: str,
        *,
        success: bool,
        rows_received: int = 0,
        status_code: int | None = None,
        error_type: str = "",
        call_id: str = "",
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO basketball_provider_calls (
                    provider, endpoint, status_code, rows_received, success,
                    error_type, call_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider, endpoint, status_code, int(rows_received),
                    int(success), str(error_type), str(call_id), utc_now(),
                ),
            )

    def state(self, key: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM basketball_state WHERE key=?", (key,)
            ).fetchone()
        return "" if row is None else str(row["value"])

    def set_state(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO basketball_state(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, value, utc_now()),
            )

    def coverage_summary(self) -> dict[str, Any]:
        with self._connect() as connection:
            games = int(connection.execute(
                "SELECT COUNT(*) FROM basketball_games"
            ).fetchone()[0])
            finished = int(connection.execute(
                "SELECT COUNT(*) FROM basketball_settlements "
                "WHERE status='SETTLED' AND quality_status='PASS'"
            ).fetchone()[0])
            odds_games = int(connection.execute(
                "SELECT COUNT(DISTINCT game_id) FROM basketball_odds"
            ).fetchone()[0])
            odds_quotes = int(connection.execute(
                "SELECT COUNT(*) FROM basketball_odds"
            ).fetchone()[0])
            settlements = int(connection.execute(
                "SELECT COUNT(*) FROM basketball_settlements"
            ).fetchone()[0])
            quarantine = int(connection.execute(
                "SELECT COUNT(*) FROM basketball_quarantine"
            ).fetchone()[0])
            calls = connection.execute(
                "SELECT COUNT(*), SUM(success), "
                "SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) "
                "FROM basketball_provider_calls"
            ).fetchone()
        return {
            "games_total": games,
            "games_quality_settled": finished,
            "games_with_odds": odds_games,
            "odds_quotes": odds_quotes,
            "settlements_total": settlements,
            "quarantined": quarantine,
            "provider_calls": int(calls[0] or 0),
            "provider_success": int(calls[1] or 0),
            "provider_failed": int(calls[2] or 0),
            "storage": str(self.db_path),
        }

    def database_integrity(self) -> bool:
        with self._connect() as connection:
            return (
                connection.execute("PRAGMA integrity_check").fetchone()[0]
                == "ok"
            )
