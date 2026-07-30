from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from storage_paths import DATA_DIR

from .domain import TennisMatch, TennisOddsQuote, utc_now


class TennisStorage:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else Path(DATA_DIR) / "tennis"
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "tennis_shadow.sqlite3"
        self._initialize()

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

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tennis_matches (
                    event_id TEXT PRIMARY KEY,
                    scheduled_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    tour TEXT NOT NULL,
                    competition_id TEXT NOT NULL,
                    competition_name TEXT NOT NULL,
                    competition_level TEXT NOT NULL,
                    competition_type TEXT NOT NULL,
                    surface TEXT NOT NULL,
                    best_of INTEGER NOT NULL,
                    player1_id TEXT NOT NULL,
                    player1_name TEXT NOT NULL,
                    player2_id TEXT NOT NULL,
                    player2_name TEXT NOT NULL,
                    player1_sets INTEGER,
                    player2_sets INTEGER,
                    winner_id TEXT NOT NULL,
                    retired INTEGER NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tennis_matches_time
                    ON tennis_matches(scheduled_at);
                CREATE INDEX IF NOT EXISTS idx_tennis_matches_players
                    ON tennis_matches(player1_id, player2_id);

                CREATE TABLE IF NOT EXISTS tennis_odds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    bookmaker TEXT NOT NULL,
                    player_name TEXT NOT NULL,
                    odds REAL NOT NULL,
                    observed_at TEXT NOT NULL,
                    source_event_id TEXT NOT NULL,
                    admitted INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(event_id, bookmaker, player_name, observed_at)
                );
                CREATE INDEX IF NOT EXISTS idx_tennis_odds_event
                    ON tennis_odds(event_id, observed_at);

                CREATE TABLE IF NOT EXISTS tennis_rankings (
                    player_id TEXT NOT NULL,
                    player_name TEXT NOT NULL,
                    tour TEXT NOT NULL,
                    rank INTEGER,
                    points INTEGER,
                    observed_at TEXT NOT NULL,
                    PRIMARY KEY(player_id, tour, observed_at)
                );
                CREATE INDEX IF NOT EXISTS idx_tennis_rankings_lookup
                    ON tennis_rankings(player_id, observed_at);

                CREATE TABLE IF NOT EXISTS tennis_predictions (
                    event_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    player1_probability REAL NOT NULL,
                    player2_probability REAL NOT NULL,
                    player1_fair_odds REAL NOT NULL,
                    player2_fair_odds REAL NOT NULL,
                    confidence REAL NOT NULL,
                    feature_quality REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(event_id, model_id, created_at)
                );

                CREATE TABLE IF NOT EXISTS tennis_picks (
                    pick_key TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    competition_name TEXT NOT NULL,
                    match_name TEXT NOT NULL,
                    outcome_player_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    model_probability REAL NOT NULL,
                    model_fair_odds REAL NOT NULL,
                    bookmaker_odds REAL NOT NULL,
                    edge REAL NOT NULL,
                    confidence REAL NOT NULL,
                    bookmaker_count INTEGER NOT NULL,
                    model_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    settled_at TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_tennis_picks_status
                    ON tennis_picks(status, created_at);

                CREATE TABLE IF NOT EXISTS tennis_candidates (
                    candidate_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    dataset_rows INTEGER NOT NULL,
                    surface_rows_json TEXT NOT NULL,
                    weights_json TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    reproducible INTEGER NOT NULL,
                    promoted_shadow INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS tennis_validations (
                    validation_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    folds INTEGER NOT NULL,
                    positive_folds INTEGER NOT NULL,
                    brier_improvement REAL NOT NULL,
                    log_loss_improvement REAL NOT NULL,
                    status TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tennis_provider_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    status_code INTEGER,
                    rows_received INTEGER NOT NULL,
                    success INTEGER NOT NULL,
                    error_type TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tennis_quarantine (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tennis_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _match_values(match: TennisMatch) -> tuple[Any, ...]:
        return (
            match.event_id, match.scheduled_at, match.status, match.tour,
            match.competition_id, match.competition_name,
            match.competition_level, match.competition_type, match.surface,
            match.best_of, match.player1_id, match.player1_name,
            match.player2_id, match.player2_name, match.player1_sets,
            match.player2_sets, match.winner_id, int(match.retired),
            json.dumps(match.raw, ensure_ascii=False, sort_keys=True), utc_now(),
        )

    def upsert_matches(self, matches: Iterable[TennisMatch]) -> int:
        rows = [self._match_values(match) for match in matches if match.event_id]
        if not rows:
            return 0
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO tennis_matches VALUES (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                )
                ON CONFLICT(event_id) DO UPDATE SET
                    scheduled_at=excluded.scheduled_at,
                    status=excluded.status,
                    tour=excluded.tour,
                    competition_id=excluded.competition_id,
                    competition_name=excluded.competition_name,
                    competition_level=excluded.competition_level,
                    competition_type=excluded.competition_type,
                    surface=excluded.surface,
                    best_of=excluded.best_of,
                    player1_id=excluded.player1_id,
                    player1_name=excluded.player1_name,
                    player2_id=excluded.player2_id,
                    player2_name=excluded.player2_name,
                    player1_sets=excluded.player1_sets,
                    player2_sets=excluded.player2_sets,
                    winner_id=excluded.winner_id,
                    retired=excluded.retired,
                    raw_json=excluded.raw_json,
                    updated_at=excluded.updated_at
                """,
                rows,
            )
        return len(rows)

    def quarantine(self, event_id: str, reason: str, payload: Any) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tennis_quarantine
                    (event_id, reason, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(event_id), str(reason),
                    json.dumps(payload, ensure_ascii=False, default=str),
                    utc_now(),
                ),
            )

    def load_matches(self) -> list[TennisMatch]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM tennis_matches ORDER BY scheduled_at"
            ).fetchall()
        return [
            TennisMatch(
                event_id=row["event_id"],
                scheduled_at=row["scheduled_at"],
                status=row["status"],
                tour=row["tour"],
                competition_id=row["competition_id"],
                competition_name=row["competition_name"],
                competition_level=row["competition_level"],
                competition_type=row["competition_type"],
                surface=row["surface"],
                best_of=int(row["best_of"]),
                player1_id=row["player1_id"],
                player1_name=row["player1_name"],
                player2_id=row["player2_id"],
                player2_name=row["player2_name"],
                player1_sets=row["player1_sets"],
                player2_sets=row["player2_sets"],
                winner_id=row["winner_id"],
                retired=bool(row["retired"]),
                raw=json.loads(row["raw_json"]),
            )
            for row in rows
        ]

    def upsert_odds(self, quotes: Iterable[TennisOddsQuote]) -> int:
        rows = [
            (
                quote.event_id, quote.bookmaker, quote.player_name,
                float(quote.odds), quote.observed_at, quote.source_event_id,
            )
            for quote in quotes
            if quote.event_id and quote.bookmaker and quote.odds > 1.0
        ]
        if not rows:
            return 0
        with self._connect() as connection:
            before = connection.total_changes
            connection.executemany(
                """
                INSERT OR IGNORE INTO tennis_odds
                    (event_id, bookmaker, player_name, odds, observed_at,
                     source_event_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            return connection.total_changes - before

    def consensus_odds(
        self, event_id: str, minimum_bookmakers: int
    ) -> dict[str, dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT player_name, bookmaker, odds, observed_at
                FROM tennis_odds
                WHERE event_id=?
                ORDER BY observed_at DESC
                """,
                (event_id,),
            ).fetchall()
        latest: dict[tuple[str, str], sqlite3.Row] = {}
        for row in rows:
            latest.setdefault((row["player_name"], row["bookmaker"]), row)
        grouped: dict[str, list[float]] = {}
        for (player, _bookmaker), row in latest.items():
            grouped.setdefault(player, []).append(float(row["odds"]))
        output: dict[str, dict[str, Any]] = {}
        for player, values in grouped.items():
            values.sort()
            count = len(values)
            median = (
                values[count // 2] if count % 2
                else (values[count // 2 - 1] + values[count // 2]) / 2
            )
            output[player] = {
                "odds": median,
                "bookmakers": count,
                "admitted": count >= minimum_bookmakers,
            }
        if len(output) == 2 and all(
            item["admitted"] for item in output.values()
        ):
            with self._connect() as connection:
                connection.execute(
                    "UPDATE tennis_odds SET admitted=1 WHERE event_id=?",
                    (event_id,),
                )
        return output

    def upsert_rankings(self, rankings: Iterable[dict[str, Any]]) -> int:
        now = utc_now()
        rows: list[tuple[Any, ...]] = []
        for ranking in rankings:
            tour = str(ranking.get("name") or ranking.get("gender") or "")
            entries = ranking.get("competitor_rankings")
            entries = entries if isinstance(entries, list) else []
            for item in entries:
                competitor = item.get("competitor")
                competitor = competitor if isinstance(competitor, dict) else {}
                player_id = str(competitor.get("id") or "")
                if player_id:
                    rows.append(
                        (
                            player_id, str(competitor.get("name") or ""), tour,
                            item.get("rank"), item.get("points"), now,
                        )
                    )
        if not rows:
            return 0
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO tennis_rankings
                    (player_id, player_name, tour, rank, points, observed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def latest_rankings(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT player_id, rank FROM tennis_rankings r
                WHERE observed_at=(
                    SELECT MAX(observed_at) FROM tennis_rankings r2
                    WHERE r2.player_id=r.player_id
                )
                """
            ).fetchall()
        return {
            row["player_id"]: int(row["rank"])
            for row in rows if row["rank"] is not None
        }

    def save_prediction(
        self,
        event_id: str,
        model_id: str,
        player1_probability: float,
        confidence: float,
        feature_quality: float,
    ) -> None:
        probability = min(0.999, max(0.001, float(player1_probability)))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO tennis_predictions VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id, model_id, probability, 1.0 - probability,
                    1.0 / probability, 1.0 / (1.0 - probability),
                    float(confidence), float(feature_quality), utc_now(),
                ),
            )

    def save_pick(
        self,
        match: TennisMatch,
        *,
        player_id: str,
        player_name: str,
        probability: float,
        bookmaker_odds: float,
        bookmaker_count: int,
        confidence: float,
        model_id: str,
    ) -> bool:
        created = utc_now()
        edge = probability * bookmaker_odds - 1.0
        key_raw = f"{match.event_id}|{player_id}|{model_id}"
        pick_key = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()[:32]
        with self._connect() as connection:
            before = connection.total_changes
            connection.execute(
                """
                INSERT OR IGNORE INTO tennis_picks (
                    pick_key, event_id, competition_name, match_name,
                    outcome_player_id, outcome, model_probability,
                    model_fair_odds, bookmaker_odds, edge, confidence,
                    bookmaker_count, model_id, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)
                """,
                (
                    pick_key, match.event_id, match.competition_name,
                    f"{match.player1_name} vs {match.player2_name}",
                    player_id, player_name, probability, 1.0 / probability,
                    bookmaker_odds, edge, confidence, bookmaker_count,
                    model_id, created,
                ),
            )
            return connection.total_changes > before

    def settle_picks(self) -> dict[str, int]:
        counts = {"settled": 0, "won": 0, "lost": 0, "void": 0}
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT p.pick_key, p.outcome_player_id, m.winner_id,
                       m.status, m.retired
                FROM tennis_picks p
                JOIN tennis_matches m ON m.event_id=p.event_id
                WHERE p.status='OPEN'
                """
            ).fetchall()
            for row in rows:
                status = str(row["status"] or "").lower()
                if bool(row["retired"]) or status in {
                    "cancelled", "canceled", "abandoned", "postponed",
                    "interrupted", "walkover", "retired",
                }:
                    result = "VOID"
                elif not row["winner_id"]:
                    continue
                elif row["outcome_player_id"] == row["winner_id"]:
                    result = "WON"
                else:
                    result = "LOST"
                connection.execute(
                    """
                    UPDATE tennis_picks
                    SET status='CLOSED', result=?, settled_at=?
                    WHERE pick_key=?
                    """,
                    (result, utc_now(), row["pick_key"]),
                )
                counts["settled"] += 1
                counts[result.lower()] += 1
        return counts

    def open_picks(self) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM tennis_picks WHERE status='OPEN' "
                "ORDER BY created_at DESC"
            ).fetchall()

    def closed_picks(self) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM tennis_picks WHERE status='CLOSED' "
                "ORDER BY created_at DESC LIMIT 500"
            ).fetchall()

    def save_candidate(
        self,
        candidate_id: str,
        dataset_rows: int,
        surface_rows: dict[str, int],
        weights: dict[str, float],
        metrics: dict[str, Any],
        reproducible: bool,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO tennis_candidates VALUES
                    (?, ?, ?, ?, ?, ?, ?, COALESCE((
                        SELECT promoted_shadow FROM tennis_candidates
                        WHERE candidate_id=?
                    ), 0))
                """,
                (
                    candidate_id, utc_now(), dataset_rows,
                    json.dumps(surface_rows, sort_keys=True),
                    json.dumps(weights, sort_keys=True),
                    json.dumps(metrics, sort_keys=True),
                    int(reproducible), candidate_id,
                ),
            )

    def save_validation(
        self,
        validation_id: str,
        candidate_id: str,
        result: dict[str, Any],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO tennis_validations VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    validation_id, candidate_id, utc_now(),
                    int(result.get("folds", 0)),
                    int(result.get("positive_folds", 0)),
                    float(result.get("brier_improvement", 0.0)),
                    float(result.get("log_loss_improvement", 0.0)),
                    str(result.get("status", "REJECTED")),
                    json.dumps(result, sort_keys=True),
                ),
            )

    def promote_shadow(self, candidate_id: str, weights: dict[str, float]) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE tennis_candidates SET promoted_shadow=1 "
                "WHERE candidate_id=?",
                (candidate_id,),
            )
        self.set_state("active_shadow_model_id", candidate_id)
        self.set_state("active_shadow_weights", json.dumps(weights, sort_keys=True))

    def active_shadow_model(self) -> tuple[str, dict[str, float]]:
        model_id = self.state("active_shadow_model_id") or "BASELINE"
        raw = self.state("active_shadow_weights")
        if raw:
            try:
                weights = json.loads(raw)
                if isinstance(weights, dict):
                    return model_id, {
                        str(key): float(value) for key, value in weights.items()
                    }
            except Exception:
                pass
        return "BASELINE", {"surface": 0.70, "general": 0.30}

    def record_provider_call(
        self,
        provider: str,
        endpoint: str,
        *,
        success: bool,
        rows_received: int = 0,
        status_code: int | None = None,
        error_type: str = "",
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tennis_provider_calls
                    (provider, endpoint, status_code, rows_received, success,
                     error_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider, endpoint, status_code, int(rows_received),
                    int(success), error_type, utc_now(),
                ),
            )

    def state(self, key: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM tennis_state WHERE key=?", (key,)
            ).fetchone()
        return "" if row is None else str(row["value"])

    def set_state(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tennis_state(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, value, utc_now()),
            )

    def coverage_summary(self) -> dict[str, Any]:
        with self._connect() as connection:
            match_rows = connection.execute(
                "SELECT status, surface, winner_id, retired FROM tennis_matches"
            ).fetchall()
            odds_events = int(connection.execute(
                "SELECT COUNT(DISTINCT event_id) FROM tennis_odds WHERE admitted=1"
            ).fetchone()[0])
            odds_quotes = int(connection.execute(
                "SELECT COUNT(*) FROM tennis_odds"
            ).fetchone()[0])
            calls = connection.execute(
                "SELECT COUNT(*), SUM(success), SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) "
                "FROM tennis_provider_calls"
            ).fetchone()
            candidates = int(connection.execute(
                "SELECT COUNT(*) FROM tennis_candidates"
            ).fetchone()[0])
            validations = int(connection.execute(
                "SELECT COUNT(*) FROM tennis_validations"
            ).fetchone()[0])
            quarantine = int(connection.execute(
                "SELECT COUNT(*) FROM tennis_quarantine"
            ).fetchone()[0])
        finished = sum(
            1 for row in match_rows
            if row["winner_id"] and not bool(row["retired"])
        )
        surface_counts = Counter(
            str(row["surface"] or "unknown") for row in match_rows
            if row["winner_id"] and not bool(row["retired"])
        )
        return {
            "matches_total": len(match_rows),
            "matches_finished_admitted": finished,
            "matches_with_consensus_odds": odds_events,
            "odds_quotes": odds_quotes,
            "surface_rows": dict(surface_counts),
            "provider_calls": int(calls[0] or 0),
            "provider_success": int(calls[1] or 0),
            "provider_failed": int(calls[2] or 0),
            "model_candidates": candidates,
            "model_validations": validations,
            "quarantined": quarantine,
            "storage": str(self.db_path),
        }

    def database_integrity(self) -> bool:
        with self._connect() as connection:
            return connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    def source_fingerprint(self) -> str:
        digest = hashlib.sha256()
        with self._connect() as connection:
            for row in connection.execute(
                "SELECT event_id, scheduled_at, winner_id, surface "
                "FROM tennis_matches ORDER BY event_id"
            ):
                digest.update("|".join(str(value) for value in row).encode("utf-8"))
        return digest.hexdigest()
