from __future__ import annotations

import json
import time
from datetime import date, timedelta

from . import SCHEMA_VERSION
from .api_sports import ApiSportsVolleyballClient, VolleyballProviderError
from .config import load_volleyball_settings
from .domain import VolleyballGame, utc_now
from .features import (
    FEATURE_SCHEMA_VERSION,
    FeatureLeakageError,
    build_point_in_time_features,
)
from .market import (
    MARKET_SCHEMA_VERSION,
    build_no_vig_consensus,
    eligible_match_winner_quotes,
)
from .settlement import profit_for_result, settle_match_winner
from .storage import VolleyballStorage


MODEL_VERSION = "volleyball-elo-shadow-v1"
RUNTIME_VERSION = "9.5"


def _fetch_days(client: ApiSportsVolleyballClient, days: list[date]):
    games: dict[str, VolleyballGame] = {}
    succeeded = 0
    failed = 0
    for day in days:
        try:
            for game in client.games_for_date(day):
                games[game.game_id] = game
            succeeded += 1
        except VolleyballProviderError:
            failed += 1
    return list(games.values()), succeeded, failed


def _best_quotes(quotes):
    best = {}
    for quote in quotes:
        current = best.get(quote.outcome)
        if current is None or quote.odds > current.odds:
            best[quote.outcome] = quote
    return best


def run_cycle(storage: VolleyballStorage, client: ApiSportsVolleyballClient, settings) -> dict:
    today = date.today()
    days = [today - timedelta(days=1), today, today + timedelta(days=1)]
    if storage.state("initial_backfill_complete") != "1" and settings.backfill_days:
        days = [today - timedelta(days=offset) for offset in range(settings.backfill_days, -1, -1)] + [
            today + timedelta(days=1)
        ]
    for raw_day in storage.open_pick_dates():
        try:
            days.append(date.fromisoformat(raw_day))
        except ValueError:
            continue
    requested_days = list(dict.fromkeys(days))
    games, days_succeeded, days_failed = _fetch_days(client, requested_days)
    if not games and days_failed:
        raise VolleyballProviderError("all volleyball game-date requests failed")
    storage.upsert_games(games)
    if settings.backfill_days and days_failed == 0:
        storage.set_state("initial_backfill_complete", "1")

    picks_created = 0
    quotes_saved = 0
    odds_attempted = 0
    odds_failed = 0
    features_saved = 0
    features_quarantined = 0
    market_consensus_saved = 0
    market_insufficient_books = 0
    for game in games:
        if game.finished or game.status.upper() not in {"NS", "NOT_STARTED", "TBD"}:
            continue
        if not storage.odds_refresh_due(
            game.game_id,
            settings.odds_refresh_hours,
            scheduled_at=game.scheduled_at,
        ):
            continue
        odds_attempted += 1
        try:
            quotes = client.odds_for_game(game.game_id)
        except VolleyballProviderError:
            odds_failed += 1
            continue
        quotes_saved += storage.save_odds(quotes)
        consensus = build_no_vig_consensus(quotes)
        if consensus is None:
            market_insufficient_books += 1
            continue
        consensus_inserted, consensus_key = storage.record_market_consensus(
            consensus.payload()
        )
        market_consensus_saved += int(consensus_inserted)
        if not consensus_key:
            market_insufficient_books += 1
            continue
        if consensus.bookmaker_count < settings.minimum_bookmakers:
            market_insufficient_books += 1
            continue
        feature_observed_at = utc_now()
        training_games, source_metadata = storage.point_in_time_training_set(
            game, feature_observed_at
        )
        try:
            bundle = build_point_in_time_features(
                game,
                training_games,
                observed_at=feature_observed_at,
                model_version=MODEL_VERSION,
                source_metadata=source_metadata,
            )
        except FeatureLeakageError as exc:
            features_quarantined += int(
                storage.record_feature_rejection(
                    game_id=game.game_id,
                    observed_at=feature_observed_at,
                    reason=str(exc),
                    details=source_metadata,
                )
            )
            continue
        inserted, feature_key, feature_status = storage.record_feature_snapshot(
            bundle.payload
        )
        features_saved += int(inserted)
        if feature_status != "PASS":
            features_quarantined += 1
            continue
        prediction = bundle.prediction
        for outcome, quote in _best_quotes(
            eligible_match_winner_quotes(quotes)
        ).items():
            probability = (
                prediction.home_probability if outcome == "HOME"
                else prediction.away_probability
            )
            fair_odds = (
                prediction.home_fair_odds if outcome == "HOME"
                else prediction.away_fair_odds
            )
            edge = quote.odds * probability - 1.0
            if edge < settings.minimum_edge:
                continue
            payload = {
                "sport": "volleyball",
                "shadow_only": True,
                "game_id": game.game_id,
                "league_name": game.league_name,
                "match_name": f"{game.home_team} vs {game.away_team}",
                "market": "MATCH_WINNER",
                "outcome": outcome,
                "bookmaker": quote.bookmaker,
                "bookmaker_odds": quote.odds,
                "model_probability": probability,
                "model_fair_odds": fair_odds,
                "bot_odds": fair_odds,
                "edge": round(edge, 8),
                "confidence": prediction.confidence,
                "model_version": MODEL_VERSION,
                "feature_key": feature_key,
                "feature_schema": FEATURE_SCHEMA_VERSION,
                "market_schema": MARKET_SCHEMA_VERSION,
                "market_consensus_key": consensus_key,
                "market_bookmaker_count": consensus.bookmaker_count,
                "market_probability": (
                    consensus.home_probability if outcome == "HOME"
                    else consensus.away_probability
                ),
                "market_fair_odds": (
                    consensus.home_fair_odds if outcome == "HOME"
                    else consensus.away_fair_odds
                ),
                "market_probability_edge": round(
                    probability
                    - (
                        consensus.home_probability if outcome == "HOME"
                        else consensus.away_probability
                    ),
                    8,
                ),
                "market_probability_dispersion": consensus.probability_dispersion,
                "home_rating": prediction.home_rating,
                "away_rating": prediction.away_rating,
                "home_matches": prediction.home_matches,
                "away_matches": prediction.away_matches,
                "generated_at": utc_now(),
                "real_execution_allowed": False,
            }
            picks_created += int(storage.create_shadow_pick(payload))

    game_index = {game.game_id: game for game in storage.load_games()}
    settled = 0
    for pick in storage.open_picks():
        game = game_index.get(str(pick["game_id"]))
        if game is None:
            continue
        result = settle_match_winner(str(pick["outcome"]), game)
        if result == "PENDING":
            continue
        profit = profit_for_result(result, float(pick["bookmaker_odds"]))
        settled += int(
            storage.close_pick(str(pick["pick_key"]), result, profit, game)
        )

    settlement_audited = 0
    settlement_mismatches = 0
    clv_recorded = 0
    for pick in storage.closed_picks():
        game = game_index.get(str(pick["game_id"]))
        if game is None:
            continue
        recalculated = settle_match_winner(str(pick["outcome"]), game)
        if recalculated in {"PENDING", "REVIEW"}:
            continue
        inserted, audit_status = storage.record_settlement_audit(
            pick, game, recalculated
        )
        settlement_audited += int(inserted)
        settlement_mismatches += int(inserted and audit_status == "MISMATCH")
        closing = storage.capture_closing_market(game)
        if closing is not None:
            clv_recorded += int(storage.record_pick_clv(pick, closing))

    coverage = storage.coverage_summary()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "HEALTHY",
        "shadow_only": True,
        "games_received": len(games),
        "quotes_saved": quotes_saved,
        "picks_created": picks_created,
        "picks_settled": settled,
        "settlement_audited": settlement_audited,
        "settlement_mismatches": settlement_mismatches,
        "days_requested": len(requested_days),
        "days_succeeded": days_succeeded,
        "days_failed": days_failed,
        "odds_attempted": odds_attempted,
        "odds_failed": odds_failed,
        "features_saved": features_saved,
        "features_quarantined": features_quarantined,
        "market_consensus_saved": market_consensus_saved,
        "market_insufficient_books": market_insufficient_books,
        "clv_recorded": clv_recorded,
        "coverage": coverage,
        "real_execution_allowed": False,
        "football_data_modified": False,
        "updated_at": utc_now(),
    }


def main() -> int:
    settings = load_volleyball_settings()
    if not settings.enabled:
        print("VOLLEYBALL v9.0 DISABLED", flush=True)
        return 0
    storage = VolleyballStorage()
    storage.initialize()
    client = ApiSportsVolleyballClient(settings, observer=storage.record_provider_call)
    print(
        f"VOLLEYBALL v{RUNTIME_VERSION} SHADOW START poll={settings.poll_minutes}m "
        f"backfill={settings.backfill_days}d",
        flush=True,
    )
    while True:
        try:
            health = run_cycle(storage, client, settings)
            storage.set_state("last_health", json.dumps(health, sort_keys=True))
            print(json.dumps({"event": "VOLLEYBALL_SHADOW_CYCLE", "runtime_version": RUNTIME_VERSION, **health}), flush=True)
        except Exception as exc:
            failure = {
                "schema_version": SCHEMA_VERSION,
                "status": "FAILED",
                "error_type": type(exc).__name__,
                "error": str(exc)[:500],
                "shadow_only": True,
                "real_execution_allowed": False,
                "football_data_modified": False,
                "updated_at": utc_now(),
            }
            storage.set_state("last_health", json.dumps(failure, sort_keys=True))
            print(json.dumps({"event": "VOLLEYBALL_SHADOW_FAILED", **failure}), flush=True)
        time.sleep(settings.poll_minutes * 60)


if __name__ == "__main__":
    raise SystemExit(main())
