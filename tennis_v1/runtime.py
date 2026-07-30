from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from .clients import (
    SportradarTennisClient,
    TennisOddsClient,
    TennisProviderError,
    TennisRateLimited,
)
from .config import TennisSettings, load_tennis_settings
from .domain import TennisMatch, TennisOddsQuote, normalize_name, utc_now
from .model import build_ratings, predict_match, validate_candidates
from .storage import TennisStorage


RUNTIME_VERSION = "tennis-shadow-v1.0"
EXCLUDED_LEVEL_WORDS = ("challenger", "itf", "junior", "doubles", "double")


def _parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except (TypeError, ValueError):
        return None


def admitted_match(match: TennisMatch, settings: TennisSettings) -> tuple[bool, str]:
    if not match.event_id or not match.player1_id or not match.player2_id:
        return False, "MISSING_IDENTIFIERS"
    if match.player1_id == match.player2_id:
        return False, "DUPLICATE_PLAYER"
    descriptor = " ".join(
        (
            match.tour,
            match.competition_name,
            match.competition_level,
            match.competition_type,
        )
    ).lower()
    if not settings.include_doubles and (
        not match.singles or "double" in descriptor
    ):
        return False, "DOUBLES_DISABLED"
    if not settings.include_challenger and "challenger" in descriptor:
        return False, "CHALLENGER_DISABLED"
    if not settings.include_itf and any(
        word in descriptor for word in ("itf", "junior")
    ):
        return False, "ITF_DISABLED"
    is_wta = "wta" in descriptor or "women" in descriptor
    is_atp = "atp" in descriptor or ("men" in descriptor and not is_wta)
    if is_wta and not settings.include_wta:
        return False, "WTA_DISABLED"
    if is_atp and not settings.include_atp:
        return False, "ATP_DISABLED"
    if not is_atp and not is_wta:
        return False, "UNSUPPORTED_TOUR"
    return True, "ADMITTED"


def _sports_keys(rows: list[dict[str, Any]], settings: TennisSettings) -> list[str]:
    chosen: list[str] = []
    for row in rows:
        key = str(row.get("key") or "")
        descriptor = f"{key} {row.get('title', '')} {row.get('description', '')}".lower()
        if not key:
            continue
        if any(word in descriptor for word in EXCLUDED_LEVEL_WORDS):
            continue
        is_wta = "wta" in descriptor or "women" in descriptor
        is_atp = "atp" in descriptor or ("tennis" in descriptor and not is_wta)
        if (is_wta and settings.include_wta) or (is_atp and settings.include_atp):
            chosen.append(key)
    return sorted(set(chosen))[: settings.maximum_odds_sports_per_cycle]


def _match_odds_event(
    event: dict[str, Any], matches: list[TennisMatch]
) -> TennisMatch | None:
    home = normalize_name(str(event.get("home_team") or ""))
    away = normalize_name(str(event.get("away_team") or ""))
    if not home or not away:
        return None
    target = {home, away}
    event_time = _parse_time(str(event.get("commence_time") or ""))
    candidates: list[tuple[float, TennisMatch]] = []
    for match in matches:
        if {
            normalize_name(match.player1_name),
            normalize_name(match.player2_name),
        } != target:
            continue
        match_time = _parse_time(match.scheduled_at)
        delta = (
            abs((match_time - event_time).total_seconds())
            if match_time and event_time
            else 0.0
        )
        if delta <= 18 * 3600:
            candidates.append((delta, match))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def _quotes_from_event(
    event: dict[str, Any], match: TennisMatch
) -> list[TennisOddsQuote]:
    now = utc_now()
    quotes: list[TennisOddsQuote] = []
    for bookmaker in event.get("bookmakers", []) or []:
        if not isinstance(bookmaker, dict):
            continue
        bookmaker_name = str(bookmaker.get("key") or bookmaker.get("title") or "")
        observed_at = str(bookmaker.get("last_update") or now)
        for market in bookmaker.get("markets", []) or []:
            if not isinstance(market, dict) or market.get("key") != "h2h":
                continue
            for outcome in market.get("outcomes", []) or []:
                if not isinstance(outcome, dict):
                    continue
                name = str(outcome.get("name") or "")
                try:
                    price = float(outcome.get("price"))
                except (TypeError, ValueError):
                    continue
                normalized = normalize_name(name)
                if normalized == normalize_name(match.player1_name):
                    player_name = match.player1_name
                elif normalized == normalize_name(match.player2_name):
                    player_name = match.player2_name
                else:
                    continue
                if 1.01 <= price <= 100.0:
                    quotes.append(
                        TennisOddsQuote(
                            event_id=match.event_id,
                            bookmaker=bookmaker_name,
                            player_name=player_name,
                            odds=price,
                            observed_at=observed_at,
                            source_event_id=str(event.get("id") or ""),
                        )
                    )
    return quotes


def _fetch_matches(
    settings: TennisSettings,
    storage: TennisStorage,
    client: SportradarTennisClient,
) -> dict[str, int]:
    today = datetime.now(timezone.utc).date()
    first_cycle = storage.state("initial_backfill_complete") != "1"
    start = today - timedelta(days=settings.backfill_days if first_cycle else 1)
    end = today + timedelta(days=settings.lookahead_days)
    accepted: list[TennisMatch] = []
    rejected = 0
    day = start
    while day <= end:
        day_text = day.isoformat()
        try:
            payloads = client.daily_summaries(day_text)
            storage.record_provider_call(
                "sportradar", f"daily_summaries:{day_text}",
                success=True, rows_received=len(payloads), status_code=200,
            )
        except TennisRateLimited:
            storage.record_provider_call(
                "sportradar", f"daily_summaries:{day_text}",
                success=False, status_code=429, error_type="RATE_LIMIT",
            )
            raise
        except TennisProviderError as exc:
            storage.record_provider_call(
                "sportradar", f"daily_summaries:{day_text}",
                success=False, status_code=exc.status_code,
                error_type=type(exc).__name__,
            )
            day += timedelta(days=1)
            continue
        for payload in payloads:
            try:
                match = TennisMatch.from_sportradar(payload)
                admitted, reason = admitted_match(match, settings)
            except Exception:
                storage.quarantine("", "PARSE_ERROR", payload)
                rejected += 1
                continue
            if admitted:
                accepted.append(match)
            else:
                storage.quarantine(match.event_id, reason, payload)
                rejected += 1
        day += timedelta(days=1)
    stored = storage.upsert_matches(accepted)
    if first_cycle:
        storage.set_state("initial_backfill_complete", "1")
    return {"accepted": stored, "rejected": rejected}


def _fetch_rankings(
    storage: TennisStorage, client: SportradarTennisClient
) -> int:
    week = datetime.now(timezone.utc).strftime("%G-W%V")
    if storage.state("rankings_week") == week:
        return 0
    try:
        rows = client.rankings()
        storage.record_provider_call(
            "sportradar", "rankings", success=True,
            rows_received=len(rows), status_code=200,
        )
        stored = storage.upsert_rankings(rows)
        storage.set_state("rankings_week", week)
        return stored
    except TennisRateLimited:
        storage.record_provider_call(
            "sportradar", "rankings", success=False,
            status_code=429, error_type="RATE_LIMIT",
        )
        return 0
    except TennisProviderError as exc:
        storage.record_provider_call(
            "sportradar", "rankings", success=False,
            status_code=exc.status_code, error_type=type(exc).__name__,
        )
        return 0


def _fetch_odds(
    settings: TennisSettings,
    storage: TennisStorage,
    client: TennisOddsClient,
    matches: list[TennisMatch],
) -> dict[str, int]:
    try:
        sports = client.active_tennis_sports()
        storage.record_provider_call(
            "the_odds_api", "sports", success=True,
            rows_received=len(sports), status_code=200,
        )
    except TennisProviderError as exc:
        storage.record_provider_call(
            "the_odds_api", "sports", success=False,
            status_code=exc.status_code, error_type=type(exc).__name__,
        )
        return {"sports": 0, "quotes": 0, "matched_events": 0}
    quotes: list[TennisOddsQuote] = []
    matched_events = 0
    keys = _sports_keys(sports, settings)
    for key in keys:
        try:
            events, _headers = client.odds(key)
            storage.record_provider_call(
                "the_odds_api", f"odds:{key}", success=True,
                rows_received=len(events), status_code=200,
            )
        except TennisRateLimited:
            storage.record_provider_call(
                "the_odds_api", f"odds:{key}", success=False,
                status_code=429, error_type="RATE_LIMIT",
            )
            break
        except TennisProviderError as exc:
            storage.record_provider_call(
                "the_odds_api", f"odds:{key}", success=False,
                status_code=exc.status_code, error_type=type(exc).__name__,
            )
            continue
        for event in events:
            match = _match_odds_event(event, matches)
            if match is None:
                continue
            matched_events += 1
            quotes.extend(_quotes_from_event(event, match))
    return {
        "sports": len(keys),
        "quotes": storage.upsert_odds(quotes),
        "matched_events": matched_events,
    }


def _predict_and_settle(
    settings: TennisSettings, storage: TennisStorage, matches: list[TennisMatch]
) -> dict[str, Any]:
    model_id, weights = storage.active_shadow_model()
    ratings = build_ratings(matches)
    predictions = 0
    picks = 0
    for match in matches:
        if match.finished or match.void:
            continue
        probability = predict_match(match, ratings, weights)
        storage.save_prediction(
            match.event_id, model_id,
            probability["player1_probability"],
            probability["confidence"],
            probability["feature_quality"],
        )
        predictions += 1
        consensus = storage.consensus_odds(
            match.event_id, settings.minimum_bookmakers
        )
        options = (
            (
                match.player1_id, match.player1_name,
                probability["player1_probability"],
            ),
            (
                match.player2_id, match.player2_name,
                probability["player2_probability"],
            ),
        )
        best: tuple[str, str, float, float, int] | None = None
        for player_id, player_name, model_probability in options:
            market = consensus.get(player_name, {})
            if not market.get("admitted"):
                continue
            odds = float(market.get("odds", 0.0))
            books = int(market.get("bookmakers", 0))
            if not 1.15 <= odds <= 3.50:
                continue
            edge = model_probability * odds - 1.0
            if edge < settings.minimum_edge:
                continue
            candidate = (player_id, player_name, model_probability, odds, books)
            if best is None or edge > best[2] * best[3] - 1.0:
                best = candidate
        if best and probability["feature_quality"] >= 0.35:
            picks += int(
                storage.save_pick(
                    match,
                    player_id=best[0], player_name=best[1],
                    probability=best[2], bookmaker_odds=best[3],
                    bookmaker_count=best[4],
                    confidence=probability["confidence"],
                    model_id=model_id,
                )
            )
    return {
        "predictions": predictions,
        "new_picks": picks,
        "settlement": storage.settle_picks(),
        "active_shadow_model_id": model_id,
    }


def _validate(
    settings: TennisSettings, storage: TennisStorage, matches: list[TennisMatch]
) -> dict[str, Any]:
    finished = sum(1 for match in matches if match.finished and not match.void)
    last_rows = int(storage.state("last_validation_rows") or 0)
    if finished - last_rows < settings.training_min_new_matches:
        return {
            "status": "WAITING_NEW_SETTLED_MATCHES",
            "dataset_rows": finished,
            "new_rows": finished - last_rows,
            "minimum_new_rows": settings.training_min_new_matches,
        }
    result = validate_candidates(
        matches,
        minimum_rows=settings.training_min_matches,
        minimum_surface_rows=settings.training_min_surface_matches,
        test_rows=settings.validation_test_matches,
        minimum_folds=settings.validation_min_folds,
        minimum_brier_improvement=settings.validation_min_brier_improvement,
    )
    candidate_id = str(result.get("candidate_id") or "")
    if candidate_id:
        storage.save_candidate(
            candidate_id,
            int(result.get("dataset_rows", 0)),
            dict(result.get("surface_rows", {})),
            dict(result.get("weights", {})),
            result,
            bool(result.get("reproducible", False)),
        )
        storage.save_validation(
            str(result.get("validation_id") or candidate_id),
            candidate_id,
            result,
        )
        if (
            result.get("status") == "POSITIVE"
            and settings.autonomous_governor_enabled
            and result.get("reproducible")
        ):
            storage.promote_shadow(candidate_id, dict(result["weights"]))
            result["shadow_promoted"] = True
    storage.set_state("last_validation_rows", str(finished))
    return result


def run_cycle(
    settings: TennisSettings | None = None,
    storage: TennisStorage | None = None,
) -> dict[str, Any]:
    config = settings or load_tennis_settings()
    store = storage or TennisStorage()
    if not config.enabled:
        return {
            "status": "DISABLED", "runtime_version": RUNTIME_VERSION,
            "shadow_only": True, "real_execution_allowed": False,
        }
    radar = SportradarTennisClient(config)
    odds = TennisOddsClient(config)
    provider_state = "HEALTHY"
    try:
        match_stats = _fetch_matches(config, store, radar)
    except TennisRateLimited:
        match_stats = {"accepted": 0, "rejected": 0}
        provider_state = "SPORTRADAR_RATE_LIMITED"
    ranking_rows = _fetch_rankings(store, radar)
    matches = store.load_matches()
    odds_stats = _fetch_odds(config, store, odds, matches)
    model_stats = _predict_and_settle(config, store, matches)
    validation = _validate(config, store, matches)
    active_model_id, _ = store.active_shadow_model()
    health = {
        "schema_version": "betbot.tennis.health.v1.0",
        "runtime_version": RUNTIME_VERSION,
        "generated_at": utc_now(),
        "status": provider_state,
        "shadow_only": True,
        "real_execution_allowed": False,
        "automatic_real_promotion_allowed": False,
        "automatic_shadow_promotion_allowed": bool(
            config.autonomous_governor_enabled
        ),
        "other_sports_modified": False,
        "provider_keys": {
            "sportradar_configured": bool(config.sportradar_api_key),
            "the_odds_api_configured": bool(config.odds_api_key),
        },
        "matches": match_stats,
        "ranking_rows": ranking_rows,
        "odds": odds_stats,
        "model": model_stats,
        "validation": validation,
        "active_shadow_model_id": active_model_id,
        "candidate_dataset_rows": int(
            validation.get("dataset_rows", 0)
        ),
        "candidate_minimum_rows": config.training_min_matches,
        "database_integrity": store.database_integrity(),
        "source_fingerprint": store.source_fingerprint(),
        "coverage": store.coverage_summary(),
    }
    store.set_state("last_health", json.dumps(health, sort_keys=True))
    return health


def main() -> int:
    settings = load_tennis_settings()
    print(
        json.dumps(
            {
                "event": "TENNIS_SHADOW_START",
                "runtime_version": RUNTIME_VERSION,
                "enabled": settings.enabled,
                "shadow_only": True,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    if not settings.enabled:
        return 0
    while True:
        try:
            health = run_cycle(settings)
            print(
                json.dumps(
                    {
                        "event": "TENNIS_SHADOW_CYCLE",
                        "status": health["status"],
                        "coverage": health["coverage"],
                        "validation": health["validation"].get("status"),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "event": "TENNIS_SHADOW_ERROR",
                        "error_type": type(exc).__name__,
                        "message_hash": hashlib.sha256(
                            str(exc).encode("utf-8")
                        ).hexdigest()[:12],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        time.sleep(settings.poll_minutes * 60)


if __name__ == "__main__":
    raise SystemExit(main())
