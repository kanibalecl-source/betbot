from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from .clients import (
    TennisAuthorizationError,
    TennisEndpointUnavailable,
    SportradarTennisClient,
    TennisOddsClient,
    TennisProviderError,
    TennisRateLimited,
)
from .config import TennisSettings, load_tennis_settings
from .domain import TennisMatch, TennisOddsQuote, normalize_name, utc_now
from .model import build_ratings, predict_match, validate_candidates
from .storage import TennisStorage


RUNTIME_VERSION = "tennis-shadow-v1.1-provider-recovery"
EXCLUDED_LEVEL_WORDS = ("challenger", "itf", "junior", "doubles", "double")


def _parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except (TypeError, ValueError):
        return None


def _provider_error_type(exc: TennisProviderError) -> str:
    return str(getattr(exc, "category", "") or type(exc).__name__).upper()


def _score_number(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _odds_player_id(name: str) -> str:
    normalized = normalize_name(name)
    return "odds-player:" + hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()[:20]


def _match_from_odds_event(
    event: dict[str, Any],
    sport: dict[str, Any],
) -> TennisMatch | None:
    event_id = str(event.get("id") or "").strip()
    player1 = str(event.get("home_team") or "").strip()
    player2 = str(event.get("away_team") or "").strip()
    scheduled_at = str(event.get("commence_time") or "").strip()
    if not event_id or not player1 or not player2 or not scheduled_at:
        return None
    descriptor = " ".join(
        (
            str(sport.get("key") or ""),
            str(sport.get("title") or ""),
            str(sport.get("description") or ""),
        )
    ).lower()
    tour = "WTA" if ("wta" in descriptor or "women" in descriptor) else "ATP"
    completed = bool(event.get("completed"))
    scores = event.get("scores")
    scores = scores if isinstance(scores, list) else []
    by_name: dict[str, float] = {}
    for score in scores:
        if not isinstance(score, dict):
            continue
        number = _score_number(score.get("score"))
        name = normalize_name(str(score.get("name") or ""))
        if name and number is not None:
            by_name[name] = number
    player1_score = by_name.get(normalize_name(player1))
    player2_score = by_name.get(normalize_name(player2))
    player1_id = _odds_player_id(player1)
    player2_id = _odds_player_id(player2)
    winner_id = ""
    if completed and player1_score is not None and player2_score is not None:
        if player1_score > player2_score:
            winner_id = player1_id
        elif player2_score > player1_score:
            winner_id = player2_id
    return TennisMatch(
        event_id=f"odds:{event_id}",
        scheduled_at=scheduled_at,
        status="closed" if completed and winner_id else "not_started",
        tour=tour,
        competition_id=str(sport.get("key") or ""),
        competition_name=str(
            sport.get("title") or event.get("sport_title") or sport.get("key") or tour
        ),
        competition_level=tour,
        competition_type="singles",
        surface="unknown",
        best_of=3,
        player1_id=player1_id,
        player1_name=player1,
        player2_id=player2_id,
        player2_name=player2,
        player1_sets=int(player1_score) if player1_score is not None else None,
        player2_sets=int(player2_score) if player2_score is not None else None,
        winner_id=winner_id,
        retired=False,
        raw={"provider": "the_odds_api", **event},
    )


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
) -> dict[str, int | bool]:
    today = datetime.now(timezone.utc).date()
    first_cycle = storage.state("initial_backfill_complete") != "1"
    requested_backfill = settings.backfill_days if first_cycle else 1
    adaptive_backfill = min(
        requested_backfill,
        max(0, settings.sportradar_max_schedule_days - settings.lookahead_days - 1),
    )
    start = today - timedelta(days=adaptive_backfill)
    end = today + timedelta(days=settings.lookahead_days)
    accepted: list[TennisMatch] = []
    rejected = 0
    successful_days = 0
    unavailable_days = 0
    failed_days = 0
    authorization_blocked = False
    day = start
    while day <= end:
        day_text = day.isoformat()
        try:
            payloads = client.daily_summaries(day_text)
            storage.record_provider_call(
                "sportradar", f"daily_summaries:{day_text}",
                success=True, rows_received=len(payloads), status_code=200,
            )
            successful_days += 1
        except TennisRateLimited:
            storage.record_provider_call(
                "sportradar", f"daily_summaries:{day_text}",
                success=False, status_code=429, error_type="RATE_LIMIT",
            )
            raise
        except TennisEndpointUnavailable as exc:
            storage.record_provider_call(
                "sportradar", f"daily_summaries:{day_text}",
                success=False,
                status_code=exc.status_code,
                error_type="DATE_UNAVAILABLE",
            )
            unavailable_days += 1
            day += timedelta(days=1)
            continue
        except TennisAuthorizationError as exc:
            storage.record_provider_call(
                "sportradar", f"daily_summaries:{day_text}",
                success=False,
                status_code=exc.status_code,
                error_type="AUTHORIZATION",
            )
            failed_days += 1
            authorization_blocked = True
            break
        except TennisProviderError as exc:
            storage.record_provider_call(
                "sportradar", f"daily_summaries:{day_text}",
                success=False, status_code=exc.status_code,
                error_type=_provider_error_type(exc),
            )
            failed_days += 1
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
    if first_cycle and successful_days:
        storage.set_state("initial_backfill_complete", "1")
    return {
        "accepted": stored,
        "rejected": rejected,
        "successful_days": successful_days,
        "unavailable_days": unavailable_days,
        "failed_days": failed_days,
        "authorization_blocked": authorization_blocked,
    }


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
            status_code=exc.status_code, error_type=_provider_error_type(exc),
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
            status_code=exc.status_code, error_type=_provider_error_type(exc),
        )
        return {
            "sports": 0, "quotes": 0, "matched_events": 0,
            "fallback_matches": 0, "scores_received": 0,
        }
    quotes: list[TennisOddsQuote] = []
    matched_events = 0
    fallback_matches: dict[str, TennisMatch] = {}
    scores_received = 0
    sport_by_key = {
        str(item.get("key") or ""): item for item in sports
        if isinstance(item, dict) and item.get("key")
    }
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
                status_code=exc.status_code, error_type=_provider_error_type(exc),
            )
            continue
        for event in events:
            match = _match_odds_event(event, matches)
            if match is None:
                match = _match_from_odds_event(event, sport_by_key.get(key, {}))
                if match is None:
                    continue
                fallback_matches[match.event_id] = match
            matched_events += 1
            quotes.extend(_quotes_from_event(event, match))
        try:
            score_rows = client.scores(key)
            storage.record_provider_call(
                "the_odds_api", f"scores:{key}", success=True,
                rows_received=len(score_rows), status_code=200,
            )
            scores_received += len(score_rows)
        except TennisRateLimited:
            storage.record_provider_call(
                "the_odds_api", f"scores:{key}", success=False,
                status_code=429, error_type="RATE_LIMIT",
            )
            break
        except TennisProviderError as exc:
            storage.record_provider_call(
                "the_odds_api", f"scores:{key}", success=False,
                status_code=exc.status_code, error_type=_provider_error_type(exc),
            )
            score_rows = []
        known_matches = matches + list(fallback_matches.values())
        for event in score_rows:
            score_match = _match_odds_event(event, known_matches)
            fallback = _match_from_odds_event(
                event, sport_by_key.get(key, {})
            )
            if fallback is None:
                continue
            if score_match is None or score_match.event_id.startswith("odds:"):
                fallback_matches[fallback.event_id] = fallback
    fallback_rows = storage.upsert_matches(fallback_matches.values())
    stored_quotes = storage.upsert_odds(quotes)
    return {
        "sports": len(keys),
        "quotes": stored_quotes,
        "matched_events": matched_events,
        "fallback_matches": fallback_rows,
        "scores_received": scores_received,
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
        match_stats = {
            "accepted": 0, "rejected": 0, "successful_days": 0,
            "unavailable_days": 0, "failed_days": 1,
            "authorization_blocked": False,
        }
        provider_state = "SPORTRADAR_RATE_LIMITED"
    ranking_rows = (
        0
        if bool(match_stats.get("authorization_blocked"))
        or provider_state == "SPORTRADAR_RATE_LIMITED"
        else _fetch_rankings(store, radar)
    )
    matches = store.load_matches()
    odds_stats = _fetch_odds(config, store, odds, matches)
    matches = store.load_matches()
    if (
        provider_state != "HEALTHY"
        and int(odds_stats.get("fallback_matches", 0)) > 0
    ):
        provider_state = "HEALTHY_ODDS_FALLBACK"
    elif bool(match_stats.get("authorization_blocked")):
        provider_state = (
            "HEALTHY_ODDS_FALLBACK"
            if int(odds_stats.get("fallback_matches", 0)) > 0
            else "SPORTRADAR_AUTHORIZATION_BLOCKED"
        )
    elif (
        int(match_stats.get("failed_days", 0)) > 0
        and int(odds_stats.get("fallback_matches", 0)) > 0
    ):
        provider_state = "HEALTHY_ODDS_FALLBACK"
    elif int(match_stats.get("failed_days", 0)) > 0:
        provider_state = "DEGRADED_PROVIDER"
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
