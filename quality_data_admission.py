"""Fail-closed admission controls for autonomous model training.

Only records satisfying immutable identity, chronology, feature quality and
settlement-evidence requirements may enter the derived training dataset.
Rejected records are safe to quarantine, but are never repaired or imputed.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


HEX64 = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_SQLITE_TABLES = {
    "picks_history",
    "results_history",
    "bet_history",
    "settled_picks",
    "settlements",
}


def parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def canonical_timestamp(value: Any) -> str:
    parsed = parse_utc(value)
    return parsed.isoformat().replace("+00:00", "Z") if parsed else ""


def _float(value: Any) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def canonical_event_key(row: Mapping[str, Any]) -> str:
    fixture = str(row.get("fixture_id") or "").strip().lower()
    kickoff = canonical_timestamp(row.get("kickoff") or row.get("timestamp"))
    market = str(row.get("market") or "").strip().upper()
    selection = str(row.get("selection") or market).strip().upper()
    sport = str(row.get("sport") or "football").strip().lower()
    # A settled economic outcome is independent of the file, provider and
    # bookmaker that reported it. Kickoff is only a fallback when no immutable
    # provider fixture id exists.
    raw = "|".join((fixture, "" if fixture else kickoff, market, selection, sport))
    return hashlib.sha256(raw.encode("utf-8", errors="strict")).hexdigest()[:32]


def allowed_sqlite_tables() -> set[str]:
    configured = {
        item.strip()
        for item in os.getenv("BETBOT_QUALITY_ALLOWED_SQLITE_TABLES", "").split(",")
        if item.strip()
    }
    return DEFAULT_SQLITE_TABLES | configured


def source_name_allowed(path: Path) -> bool:
    name = path.name.lower()
    hints = tuple(
        item.strip().lower()
        for item in os.getenv(
            "BETBOT_QUALITY_ALLOWED_SOURCE_HINTS",
            "history,settled,settlement",
        ).split(",")
        if item.strip()
    )
    return any(hint in name for hint in hints)


def verify_settlement_evidence(path: Path) -> tuple[set[str], list[str]]:
    """Verify payload hashes and the complete append-only hash chain."""
    valid: set[str] = set()
    errors: list[str] = []
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='settlement_evidence'"
        ).fetchone()
        if not exists:
            return valid, ["settlement_evidence_table_missing"]
        previous = "GENESIS"
        rows = connection.execute(
            "SELECT * FROM settlement_evidence ORDER BY id ASC"
        ).fetchall()
        for row in rows:
            item = dict(row)
            payload = str(item.get("payload_json") or "")
            payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if payload_hash != str(item.get("payload_sha256") or ""):
                errors.append(f"payload_hash_mismatch:{item.get('id')}")
                previous = str(item.get("evidence_hash") or "")
                continue
            if str(item.get("previous_evidence_hash") or "") != previous:
                errors.append(f"chain_link_mismatch:{item.get('id')}")
                previous = str(item.get("evidence_hash") or "")
                continue
            body = {
                "pick_id": int(item["pick_id"]),
                "pick_key": str(item["pick_key"]),
                "fixture_id": str(item["fixture_id"]),
                "settled_at": str(item["settled_at"]),
                "provider": str(item["provider"]),
                "provider_status": str(item["provider_status"]),
                "home_goals": int(item["home_goals"]),
                "away_goals": int(item["away_goals"]),
                "result": str(item["result"]),
                "payload_sha256": str(item["payload_sha256"]),
                "previous_evidence_hash": previous,
            }
            expected = hashlib.sha256(
                json.dumps(
                    body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest()
            actual = str(item.get("evidence_hash") or "")
            if expected != actual:
                errors.append(f"evidence_hash_mismatch:{item.get('id')}")
            else:
                valid.add(actual)
            previous = actual
    except (sqlite3.DatabaseError, KeyError, TypeError, ValueError) as exc:
        errors.append(f"evidence_verification_error:{type(exc).__name__}")
    finally:
        if connection is not None:
            connection.close()
    return valid, errors


def admission_reasons(
    row: Mapping[str, Any],
    *,
    verified_evidence_hashes: set[str] | None = None,
    expected_sport: str | None = None,
) -> list[str]:
    reasons: list[str] = []
    if parse_utc(row.get("timestamp")) is None:
        reasons.append("invalid_utc_timestamp")
    if not str(row.get("fixture_id") or "").strip():
        reasons.append("missing_fixture_id")
    if not str(row.get("market") or "").strip():
        reasons.append("missing_market")
    for key in (
        "current_probability",
        "dixon_coles_probability",
        "market_probability",
    ):
        value = _float(row.get(key))
        if value is None or not 0.0 < value < 1.0:
            reasons.append(f"invalid_{key}")
    for key in ("home_xg", "away_xg"):
        value = _float(row.get(key))
        if value is None or not 0.0 <= value <= 15.0:
            reasons.append(f"invalid_{key}")
    odds = _float(row.get("odds"))
    if odds is None or not 1.0 < odds <= 1000.0:
        reasons.append("invalid_odds")
    minimum_quality = float(os.getenv("BETBOT_QUALITY_MIN_DATA_QUALITY", "0.65"))
    quality = _float(row.get("data_quality"))
    if quality is None or quality < minimum_quality or quality > 1.0:
        reasons.append("insufficient_data_quality")
    for key in ("strategy_version", "model_version", "prediction_snapshot_id"):
        if not str(row.get(key) or "").strip():
            reasons.append(f"missing_{key}")
    evidence_hash = str(row.get("settlement_evidence_hash") or "").lower()
    payload_hash = str(row.get("settlement_payload_sha256") or "").lower()
    if not HEX64.fullmatch(evidence_hash):
        reasons.append("missing_or_invalid_settlement_evidence_hash")
    if not HEX64.fullmatch(payload_hash):
        reasons.append("missing_or_invalid_settlement_payload_hash")
    if verified_evidence_hashes is not None and evidence_hash not in verified_evidence_hashes:
        reasons.append("settlement_evidence_not_verified")
    sport = str(row.get("sport") or "football").strip().lower()
    required_sport = str(
        expected_sport
        or os.getenv("BETBOT_QUALITY_EXPECTED_SPORT", "football")
    ).strip().lower()
    if required_sport not in {"football", "volleyball", "handball"}:
        reasons.append("unsupported_expected_sport")
    elif sport != required_sport:
        reasons.append("sport_dataset_contamination")
    return sorted(set(reasons))
