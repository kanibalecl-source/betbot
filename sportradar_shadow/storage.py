from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from runtime_health_v81 import atomic_json
from storage_paths import DATA_DIR

from . import SCHEMA_VERSION
from .normalize import canonical_json, fingerprint


class SportradarShadowStorage:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else DATA_DIR / "sportradar_shadow"
        self.database_path = self.root / "sportradar_shadow.sqlite3"
        self.health_path = self.root / "sportradar_shadow_health.json"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS event_snapshots (
                    snapshot_key TEXT PRIMARY KEY,
                    sport TEXT NOT NULL,
                    provider_event_id TEXT NOT NULL,
                    scheduled_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    home_team TEXT NOT NULL,
                    away_team TEXT NOT NULL,
                    home_team_id TEXT NOT NULL,
                    away_team_id TEXT NOT NULL,
                    competition_id TEXT NOT NULL,
                    competition_name TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    inserted_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sr_event_lookup
                    ON event_snapshots(sport, provider_event_id, observed_at);

                CREATE TABLE IF NOT EXISTS odds_snapshots (
                    quote_key TEXT PRIMARY KEY,
                    sport TEXT NOT NULL,
                    provider_event_id TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    market_name TEXT NOT NULL,
                    bookmaker_id TEXT NOT NULL,
                    bookmaker TEXT NOT NULL,
                    outcome_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    decimal_odds REAL NOT NULL,
                    handicap TEXT,
                    observed_at TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    inserted_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sr_odds_lookup
                    ON odds_snapshots(
                        sport, provider_event_id, market_id, bookmaker_id, observed_at
                    );

                CREATE TABLE IF NOT EXISTS quarantine (
                    quarantine_key TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    sport TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    reasons_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    inserted_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS provider_calls (
                    call_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    attempt INTEGER NOT NULL,
                    success INTEGER NOT NULL,
                    error_type TEXT NOT NULL,
                    observed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runtime_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TRIGGER IF NOT EXISTS sr_event_no_update
                BEFORE UPDATE ON event_snapshots
                BEGIN SELECT RAISE(ABORT, 'sportradar event snapshots are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS sr_event_no_delete
                BEFORE DELETE ON event_snapshots
                BEGIN SELECT RAISE(ABORT, 'sportradar event snapshots are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS sr_odds_no_update
                BEFORE UPDATE ON odds_snapshots
                BEGIN SELECT RAISE(ABORT, 'sportradar odds snapshots are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS sr_odds_no_delete
                BEFORE DELETE ON odds_snapshots
                BEGIN SELECT RAISE(ABORT, 'sportradar odds snapshots are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS sr_quarantine_no_update
                BEFORE UPDATE ON quarantine
                BEGIN SELECT RAISE(ABORT, 'sportradar quarantine is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS sr_quarantine_no_delete
                BEFORE DELETE ON quarantine
                BEGIN SELECT RAISE(ABORT, 'sportradar quarantine is append-only'); END;
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def record_provider_call(self, event: dict[str, Any]) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO provider_calls(
                    url, status_code, duration_ms, attempt, success,
                    error_type, observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.get("url", ""))[:1000],
                    int(event.get("status_code", 0)),
                    int(event.get("duration_ms", 0)),
                    int(event.get("attempt", 1)),
                    int(bool(event.get("success", False))),
                    str(event.get("error_type", ""))[:100],
                    self._now(),
                ),
            )

    def save_events(self, rows: Iterable[dict[str, Any]]) -> int:
        inserted = 0
        now = self._now()
        with self._connection() as connection:
            for row in rows:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO event_snapshots(
                        snapshot_key, sport, provider_event_id, scheduled_at,
                        status, home_team, away_team, home_team_id, away_team_id,
                        competition_id, competition_name, observed_at,
                        payload_sha256, payload_json, inserted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["snapshot_key"],
                        row["sport"],
                        row["provider_event_id"],
                        row["scheduled_at"],
                        row["status"],
                        row["home_team"],
                        row["away_team"],
                        row["home_team_id"],
                        row["away_team_id"],
                        row["competition_id"],
                        row["competition_name"],
                        row["observed_at"],
                        row["payload_sha256"],
                        canonical_json(row["raw"]),
                        now,
                    ),
                )
                inserted += int(cursor.rowcount == 1)
        return inserted

    def save_odds(self, rows: Iterable[dict[str, Any]]) -> int:
        inserted = 0
        now = self._now()
        with self._connection() as connection:
            for row in rows:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO odds_snapshots(
                        quote_key, sport, provider_event_id, market_id,
                        market_name, bookmaker_id, bookmaker, outcome_id,
                        outcome, decimal_odds, handicap, observed_at,
                        payload_sha256, payload_json, inserted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["quote_key"],
                        row["sport"],
                        row["provider_event_id"],
                        row["market_id"],
                        row["market_name"],
                        row["bookmaker_id"],
                        row["bookmaker"],
                        row["outcome_id"],
                        row["outcome"],
                        row["decimal_odds"],
                        (
                            None
                            if row.get("handicap") is None
                            else str(row.get("handicap"))
                        ),
                        row["observed_at"],
                        row["payload_sha256"],
                        canonical_json(row["raw"]),
                        now,
                    ),
                )
                inserted += int(cursor.rowcount == 1)
        return inserted

    def quarantine(self, rows: Iterable[dict[str, Any]]) -> int:
        inserted = 0
        now = self._now()
        with self._connection() as connection:
            for row in rows:
                key = fingerprint(
                    row.get("kind"),
                    row.get("sport"),
                    row.get("provider_id"),
                    row.get("reasons"),
                    row.get("raw"),
                )
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO quarantine(
                        quarantine_key, kind, sport, provider_id, reasons_json,
                        payload_json, observed_at, inserted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key,
                        str(row.get("kind", "")),
                        str(row.get("sport", "")),
                        str(row.get("provider_id", "")),
                        canonical_json(row.get("reasons", [])),
                        canonical_json(row.get("raw", {})),
                        str(row.get("observed_at", now)),
                        now,
                    ),
                )
                inserted += int(cursor.rowcount == 1)
        return inserted

    def set_state(self, key: str, value: str) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO runtime_state(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, value, self._now()),
            )

    def counts(self) -> dict[str, int]:
        with self._connection() as connection:
            result = {}
            for table in (
                "event_snapshots",
                "odds_snapshots",
                "quarantine",
                "provider_calls",
            ):
                result[table] = int(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                )
        return result

    def write_health(self, payload: dict[str, Any]) -> None:
        safe = {
            **payload,
            "schema_version": SCHEMA_VERSION,
            "contains_secrets": False,
            "shadow_only": True,
            "active_model_modified": False,
            "source_history_modified": False,
            "real_execution_allowed": False,
        }
        atomic_json(self.health_path, safe)
        self.set_state("last_health", json.dumps(safe, sort_keys=True))
