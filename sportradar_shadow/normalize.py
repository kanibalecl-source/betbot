from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(*parts: Any) -> str:
    material = "|".join(canonical_json(part) for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _parse_timestamp(value: Any) -> str | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat()


def _competitor_names(event: Mapping[str, Any]) -> tuple[str, str, str, str]:
    home_name = away_name = home_id = away_id = ""
    for raw in _list(event.get("competitors")):
        item = _dict(raw)
        qualifier = str(item.get("qualifier", "")).strip().lower()
        if qualifier == "home":
            home_name = str(item.get("name", "")).strip()
            home_id = str(item.get("id", "")).strip()
        elif qualifier == "away":
            away_name = str(item.get("name", "")).strip()
            away_id = str(item.get("id", "")).strip()
    return home_name, away_name, home_id, away_id


def _summary_items(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates = (
        payload.get("summaries"),
        payload.get("sport_event_summaries"),
        payload.get("sport_events"),
        _dict(payload.get("schedule")).get("sport_events"),
    )
    for candidate in candidates:
        rows = [_dict(item) for item in _list(candidate)]
        if rows:
            return rows
    return []


def normalize_events(
    payload: Mapping[str, Any],
    *,
    sport: str,
    source_endpoint: str,
    observed_at: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    observed = (
        _parse_timestamp(payload.get("generated_at"))
        or _parse_timestamp(observed_at)
        or utc_now()
    )
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for raw_item in _summary_items(payload):
        event = _dict(raw_item.get("sport_event")) or raw_item
        status = _dict(raw_item.get("sport_event_status"))
        context = _dict(event.get("sport_event_context"))
        competition = _dict(context.get("competition")) or _dict(
            event.get("tournament")
        )
        category = _dict(context.get("category")) or _dict(
            competition.get("category")
        )
        event_id = str(event.get("id", "")).strip()
        scheduled_at = _parse_timestamp(
            event.get("start_time") or event.get("scheduled")
        )
        home_name, away_name, home_id, away_id = _competitor_names(event)
        reasons = []
        if not event_id.startswith(("sr:sport_event:", "sr:match:")):
            reasons.append("invalid_event_id")
        if scheduled_at is None:
            reasons.append("invalid_start_time")
        if not home_name or not away_name or not home_id or not away_id:
            reasons.append("missing_competitors")
        normalized = {
            "sport": sport,
            "provider": "sportradar",
            "provider_event_id": event_id,
            "scheduled_at": scheduled_at,
            "status": str(
                status.get("match_status")
                or status.get("status")
                or event.get("status")
                or ""
            ).strip(),
            "home_team": home_name,
            "away_team": away_name,
            "home_team_id": home_id,
            "away_team_id": away_id,
            "home_score": status.get("home_score"),
            "away_score": status.get("away_score"),
            "competition_id": str(competition.get("id", "")).strip(),
            "competition_name": str(competition.get("name", "")).strip(),
            "category_id": str(category.get("id", "")).strip(),
            "category_name": str(category.get("name", "")).strip(),
            "country_code": str(category.get("country_code", "")).strip(),
            "observed_at": observed,
            "source_endpoint": source_endpoint,
            "raw": raw_item,
        }
        if reasons:
            rejected.append(
                {
                    "kind": "event",
                    "sport": sport,
                    "provider_id": event_id,
                    "reasons": reasons,
                    "observed_at": observed,
                    "raw": raw_item,
                }
            )
            continue
        raw_hash = fingerprint(raw_item)
        normalized["payload_sha256"] = raw_hash
        normalized["snapshot_key"] = fingerprint(
            sport, event_id, raw_hash, "event"
        )
        accepted.append(normalized)
    return accepted, rejected


def schedule_event_ids(payload: Mapping[str, Any]) -> list[tuple[str, str]]:
    rows = _summary_items(payload)
    result: list[tuple[str, str]] = []
    for raw in rows:
        event = _dict(raw.get("sport_event")) or raw
        event_id = str(event.get("id", "")).strip()
        scheduled = _parse_timestamp(
            event.get("start_time") or event.get("scheduled")
        )
        if event_id.startswith(("sr:sport_event:", "sr:match:")) and scheduled:
            result.append((event_id, scheduled))
    return result


def _market_rows(payload: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    for key in ("markets", "sport_event_markets"):
        rows = [_dict(item) for item in _list(payload.get(key))]
        if rows:
            return rows
    event = _dict(payload.get("sport_event"))
    for key in ("markets", "sport_event_markets"):
        rows = [_dict(item) for item in _list(event.get(key))]
        if rows:
            return rows
    return []


def normalize_odds(
    payload: Mapping[str, Any],
    *,
    sport: str,
    event_id: str,
    source_endpoint: str,
    observed_at: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    observed = (
        _parse_timestamp(payload.get("generated_at"))
        or _parse_timestamp(observed_at)
        or utc_now()
    )
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for market in _market_rows(payload):
        market_id = str(market.get("id", "")).strip()
        market_name = str(market.get("name", "")).strip()
        for raw_book in _list(market.get("books")):
            book = _dict(raw_book)
            book_id = str(book.get("id", "")).strip()
            book_name = str(book.get("name", "")).strip()
            if str(book.get("removed", "")).lower() == "true":
                continue
            for raw_outcome in _list(book.get("outcomes")):
                outcome = _dict(raw_outcome)
                try:
                    decimal_odds = float(
                        outcome.get("odds_decimal")
                        or outcome.get("odds")
                        or 0
                    )
                except (TypeError, ValueError):
                    decimal_odds = 0.0
                outcome_id = str(outcome.get("id", "")).strip()
                outcome_name = str(
                    outcome.get("name")
                    or outcome.get("type")
                    or outcome.get("field_id")
                    or outcome_id
                ).strip()
                reasons = []
                if not market_id and not market_name:
                    reasons.append("missing_market")
                if not book_id or not book_name:
                    reasons.append("missing_bookmaker")
                if not outcome_id and not outcome_name:
                    reasons.append("missing_outcome")
                if not math.isfinite(decimal_odds) or not 1.0 < decimal_odds <= 100.0:
                    reasons.append("invalid_decimal_odds")
                normalized = {
                    "sport": sport,
                    "provider": "sportradar",
                    "provider_event_id": event_id,
                    "market_id": market_id,
                    "market_name": market_name,
                    "bookmaker_id": book_id,
                    "bookmaker": book_name,
                    "outcome_id": outcome_id,
                    "outcome": outcome_name,
                    "decimal_odds": decimal_odds,
                    "handicap": outcome.get("handicap"),
                    "removed": bool(outcome.get("removed", False)),
                    "observed_at": observed,
                    "source_endpoint": source_endpoint,
                    "raw": outcome,
                }
                if reasons:
                    rejected.append(
                        {
                            "kind": "odds",
                            "sport": sport,
                            "provider_id": event_id,
                            "reasons": reasons,
                            "observed_at": observed,
                            "raw": normalized,
                        }
                    )
                    continue
                raw_hash = fingerprint(outcome)
                normalized["payload_sha256"] = raw_hash
                normalized["quote_key"] = fingerprint(
                    sport,
                    event_id,
                    market_id or market_name,
                    book_id,
                    outcome_id or outcome_name,
                    decimal_odds,
                    outcome.get("handicap"),
                    observed,
                )
                accepted.append(normalized)
    return accepted, rejected

