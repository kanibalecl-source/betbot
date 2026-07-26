from __future__ import annotations

import hashlib
import json
import math
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

SPORTS = {"football", "volleyball", "handball"}
TERMINAL_RESULTS = {"WON", "LOST", "VOID", "PUSH", "PENDING", "OPEN", "CLOSED"}


class DatabaseUnavailable(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dsn() -> str:
    from app.core.config import get_settings
    settings = get_settings()
    value = str(settings.postgres_dsn or settings.database_url or "").strip()
    if not value.startswith(("postgresql://", "postgres://")):
        raise DatabaseUnavailable("PostgreSQL is not configured")
    return value


@contextmanager
def connection() -> Iterator[Any]:
    try:
        import psycopg
    except ImportError as exc:
        raise DatabaseUnavailable("psycopg is not installed") from exc
    from app.core.config import get_settings
    settings = get_settings()
    try:
        with psycopg.connect(
            _dsn(),
            connect_timeout=max(1, settings.database_connect_timeout_seconds),
            autocommit=False,
        ) as conn:
            yield conn
    except DatabaseUnavailable:
        raise
    except Exception as exc:
        raise DatabaseUnavailable(type(exc).__name__) from exc


DDL = """
CREATE TABLE IF NOT EXISTS api_picks (
    pick_id TEXT PRIMARY KEY,
    sport TEXT NOT NULL CHECK (sport IN ('football','volleyball','handball')),
    league TEXT NOT NULL,
    match_name TEXT NOT NULL,
    market TEXT NOT NULL,
    bookmaker_odds DOUBLE PRECISION NOT NULL CHECK (bookmaker_odds > 1),
    model_probability DOUBLE PRECISION NOT NULL CHECK (model_probability > 0 AND model_probability < 1),
    fair_odds DOUBLE PRECISION NOT NULL CHECK (fair_odds > 1),
    edge DOUBLE PRECISION NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
    status TEXT NOT NULL,
    result TEXT NOT NULL,
    scheduled_at TIMESTAMPTZ,
    generated_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    source TEXT NOT NULL,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS api_picks_sport_time_idx
ON api_picks (sport, generated_at DESC);
CREATE INDEX IF NOT EXISTS api_picks_status_idx
ON api_picks (sport, status, result);

CREATE TABLE IF NOT EXISTS api_status_documents (
    sport TEXT NOT NULL CHECK (sport IN ('football','volleyball','handball')),
    kind TEXT NOT NULL CHECK (kind IN ('quality','model','data_quality','runtime')),
    payload JSONB NOT NULL,
    source TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (sport, kind)
);

CREATE TABLE IF NOT EXISTS api_sync_audit (
    audit_id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    accepted INTEGER NOT NULL,
    rejected INTEGER NOT NULL,
    rejection_reasons JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def initialize_schema() -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()


def health() -> dict[str, Any]:
    try:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return {"configured": True, "reachable": True, "backend": "postgresql"}
    except DatabaseUnavailable as exc:
        from app.core.config import get_settings
        return {
            "configured": bool(str(get_settings().postgres_dsn or "").strip()),
            "reachable": False,
            "backend": "postgresql",
            "error": str(exc),
        }


def _number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _env_number(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _timestamp(value: Any, *, required: bool) -> str | None:
    text = str(value or "").strip()
    if not text:
        return utc_now() if required else None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def validate_pick(raw: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    sport = str(raw.get("sport", "")).strip().lower()
    if sport not in SPORTS:
        return None, "invalid_sport"
    match_name = str(raw.get("match_name") or raw.get("match") or "").strip()
    market = str(raw.get("market") or raw.get("typ") or "").strip()
    league = str(raw.get("league") or raw.get("league_name") or raw.get("liga") or "-").strip()
    odds = _number(raw.get("bookmaker_odds", raw.get("kurs_buk", raw.get("odds"))))
    probability = _number(raw.get("model_probability", raw.get("probability")))
    confidence = _number(raw.get("confidence"))
    if probability is not None and probability > 1:
        probability /= 100
    if not match_name or not market:
        return None, "missing_identity"
    integrity_status = str(raw.get("market_integrity_status", "")).strip().upper()
    integrity_schema = str(
        raw.get("market_integrity_schema") or raw.get("market_schema") or ""
    ).strip()
    consensus_id = str(
        raw.get("market_consensus_id") or raw.get("market_consensus_key") or ""
    ).strip()
    bookmaker_count = _number(
        raw.get("market_bookmaker_count", raw.get("bookmaker_count"))
    )
    dispersion = _number(
        raw.get("market_probability_dispersion", raw.get("probability_dispersion"))
    )
    minimum_bookmakers = max(
        1, int(_env_number(f"BETBOT_V13_{sport.upper()}_MIN_BOOKMAKERS", 2))
    )
    maximum_dispersion = _env_number(
        f"BETBOT_V13_{sport.upper()}_MAX_PROBABILITY_DISPERSION", 0.075
    )
    if integrity_status != "PASS":
        return None, "market_integrity_not_pass"
    if not integrity_schema.endswith(".v13"):
        return None, "invalid_market_integrity_schema"
    if not consensus_id:
        return None, "missing_market_consensus"
    if bookmaker_count is None or bookmaker_count < minimum_bookmakers:
        return None, "insufficient_bookmaker_consensus"
    if dispersion is None or dispersion > maximum_dispersion:
        return None, "excessive_market_dispersion"
    if sport == "football":
        if not _truthy(raw.get("bookmaker_verified")):
            return None, "unverified_bookmaker_odds"
        if str(raw.get("bookmaker_scope", "")).strip() != "POLAND_ALLOWLIST":
            return None, "invalid_bookmaker_scope"
        if str(raw.get("market_scope", "")).strip() != "FULL_MATCH":
            return None, "invalid_market_scope"
        if not str(raw.get("bookmaker") or raw.get("bookmaker_name") or "").strip():
            return None, "missing_bookmaker"
    if odds is None or odds <= 1 or odds > 100:
        return None, "invalid_odds"
    if probability is None or not 0 < probability < 1:
        return None, "invalid_probability"
    confidence = probability * 100 if confidence is None else confidence
    if confidence <= 1:
        confidence *= 100
    if not 0 <= confidence <= 100:
        return None, "invalid_confidence"
    fair_odds = _number(raw.get("fair_odds", raw.get("model_odds"))) or 1 / probability
    edge = _number(raw.get("edge"))
    edge = probability * odds - 1 if edge is None else edge
    result = str(raw.get("result", "PENDING")).strip().upper()
    status = str(raw.get("status", "OPEN")).strip().upper()
    if result not in TERMINAL_RESULTS or status not in TERMINAL_RESULTS:
        return None, "invalid_state"
    generated_at = _timestamp(
        raw.get("generated_at") or raw.get("created_at"), required=True
    )
    scheduled_at = _timestamp(raw.get("scheduled_at"), required=False)
    if generated_at is None:
        return None, "invalid_generated_at"
    if raw.get("scheduled_at") and scheduled_at is None:
        return None, "invalid_scheduled_at"
    stable = str(raw.get("pick_id") or raw.get("pick_key") or "").strip()
    if not stable:
        material = "|".join((sport, league, match_name, market, generated_at))
        stable = hashlib.sha256(material.encode("utf-8")).hexdigest()
    cleaned = {
        "pick_id": stable,
        "sport": sport,
        "league": league,
        "match_name": match_name,
        "market": market,
        "bookmaker_odds": odds,
        "model_probability": probability,
        "fair_odds": fair_odds,
        "edge": edge,
        "confidence": confidence,
        "status": status,
        "result": result,
        "scheduled_at": scheduled_at,
        "generated_at": generated_at,
        "payload": raw,
    }
    return cleaned, None


def sync_snapshot(records: list[dict[str, Any]], statuses: list[dict[str, Any]], source: str) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    reasons: dict[str, int] = {}
    for raw in records:
        record, reason = validate_pick(raw if isinstance(raw, dict) else {})
        if record is None:
            reasons[reason or "invalid_record"] = reasons.get(reason or "invalid_record", 0) + 1
        else:
            accepted.append(record)
    saved_statuses = 0
    from psycopg.types.json import Jsonb
    with connection() as conn:
        with conn.cursor() as cur:
            for row in accepted:
                cur.execute(
                    """
                    INSERT INTO api_picks
                    (pick_id,sport,league,match_name,market,bookmaker_odds,
                     model_probability,fair_odds,edge,confidence,status,result,
                     scheduled_at,generated_at,payload,source)
                    VALUES
                    (%(pick_id)s,%(sport)s,%(league)s,%(match_name)s,%(market)s,
                     %(bookmaker_odds)s,%(model_probability)s,%(fair_odds)s,
                     %(edge)s,%(confidence)s,%(status)s,%(result)s,
                     %(scheduled_at)s,%(generated_at)s,%(payload)s,%(source)s)
                    ON CONFLICT (pick_id) DO UPDATE SET
                      status=EXCLUDED.status,result=EXCLUDED.result,
                      payload=EXCLUDED.payload,synced_at=NOW()
                    """,
                    {**row, "payload": Jsonb(row["payload"]), "source": source},
                )
            for document in statuses:
                sport = str(document.get("sport", "")).lower()
                kind = str(document.get("kind", "")).lower()
                payload = document.get("payload", {})
                if sport not in SPORTS or kind not in {"quality", "model", "data_quality", "runtime"}:
                    continue
                cur.execute(
                    """
                    INSERT INTO api_status_documents (sport,kind,payload,source)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT (sport,kind) DO UPDATE SET
                      payload=EXCLUDED.payload,source=EXCLUDED.source,updated_at=NOW()
                    """,
                    (sport, kind, Jsonb(payload), source),
                )
                saved_statuses += 1
            cur.execute(
                "INSERT INTO api_sync_audit(source,accepted,rejected,rejection_reasons) VALUES (%s,%s,%s,%s)",
                (source, len(accepted), sum(reasons.values()), Jsonb(reasons)),
            )
        conn.commit()
    return {
        "accepted": len(accepted),
        "rejected": sum(reasons.values()),
        "statuses_saved": saved_statuses,
        "rejection_reasons": reasons,
        "source_history_modified": False,
    }


def list_picks(sport: str, page: int, page_size: int, status: str | None = None) -> dict[str, Any]:
    offset = (page - 1) * page_size
    clauses = ["sport=%s"]
    params: list[Any] = [sport]
    # Legacy rows remain queryable in PostgreSQL for auditability, but only
    # verified v13 consensus records are exposed as current recommendations.
    clauses.append("payload->>'market_integrity_status'='PASS'")
    clauses.append("(payload->>'market_integrity_schema') LIKE '%.v13'")
    if sport == "football":
        # Historical snapshots created before strict bookmaker provenance are
        # retained for auditability, but never exposed as actionable picks.
        clauses.append("payload->>'bookmaker_verified'='true'")
        clauses.append("payload->>'bookmaker_scope'='POLAND_ALLOWLIST'")
        clauses.append("payload->>'market_scope'='FULL_MATCH'")
    if status:
        clauses.append("status=%s")
        params.append(status.upper())
    where = " AND ".join(clauses)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM api_picks WHERE {where}", params)
            total = int(cur.fetchone()[0])
            cur.execute(
                f"""
                SELECT payload FROM api_picks WHERE {where}
                ORDER BY generated_at DESC, pick_id DESC LIMIT %s OFFSET %s
                """,
                [*params, page_size, offset],
            )
            items = [row[0] for row in cur.fetchall()]
    return {"items": items, "page": page, "page_size": page_size, "total": total}


def status_document(sport: str, kind: str) -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload,source,updated_at FROM api_status_documents WHERE sport=%s AND kind=%s",
                (sport, kind),
            )
            row = cur.fetchone()
    if not row:
        return {"available": False, "sport": sport, "kind": kind}
    return {
        "available": True,
        "sport": sport,
        "kind": kind,
        "payload": row[0],
        "source": row[1],
        "updated_at": row[2],
    }


def sync_metrics() -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(accepted),0),COALESCE(SUM(rejected),0),MAX(created_at)
                FROM api_sync_audit
                """
            )
            accepted, rejected, last_sync = cur.fetchone()
            cur.execute("SELECT sport,COUNT(*) FROM api_picks GROUP BY sport")
            sports = {row[0]: int(row[1]) for row in cur.fetchall()}
    return {
        "accepted": int(accepted),
        "rejected": int(rejected),
        "last_sync_at": last_sync,
        "records_by_sport": sports,
    }
