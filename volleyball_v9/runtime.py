from __future__ import annotations

import json
import time

from . import SCHEMA_VERSION
from .api_sports import (
    ApiSportsVolleyballClient,
    VolleyballProviderError,
    VolleyballRequestBudgetExhausted,
)
from .config import load_volleyball_settings
from .domain import VolleyballGame, utc_now
from .features import (
    FEATURE_SCHEMA_VERSION,
    FeatureLeakageError,
    build_point_in_time_features,
)
from .governor import GovernorSettings, run_autonomous_governor
from .market import (
    MARKET_SCHEMA_VERSION,
    build_no_vig_consensus,
    eligible_match_winner_quotes,
)
from .settlement import profit_for_result, settle_match_winner
from .storage import VolleyballStorage
from .training import DEFAULT_HYPERPARAMETERS, train_candidate
from .validation import ValidationSettings, validate_candidate
from multisport_quality_v12 import odds_snapshot_stage, policy_for
from market_integrity_audit_v13 import sport_training_ready
from shadow_collection_resilience_v204 import collect_games_incrementally


MODEL_VERSION = "volleyball-elo-shadow-baseline-v1"
RUNTIME_VERSION = "12.2"


def _best_quotes(quotes):
    best = {}
    for quote in quotes:
        current = best.get(quote.outcome)
        if current is None or quote.odds > current.odds:
            best[quote.outcome] = quote
    return best


def run_cycle(storage: VolleyballStorage, client: ApiSportsVolleyballClient, settings) -> dict:
    quality_policy = policy_for("volleyball")
    integrity_training_ready = sport_training_ready(
        storage.root.parent, "volleyball"
    )
    governor_enabled = settings.autonomous_governor_enabled and integrity_training_ready
    collection = collect_games_incrementally(
        storage=storage,
        client=client,
        settings=settings,
        provider_error_type=VolleyballProviderError,
        request_budget_error_type=VolleyballRequestBudgetExhausted,
        open_pick_dates=storage.open_pick_dates(),
    )
    games = collection.games
    storage.upsert_games(games)

    previous_candidate_rows = storage.latest_candidate_dataset_rows()
    candidate_required_rows = (
        max(settings.training_min_games, quality_policy.candidate_minimum_rows)
        if previous_candidate_rows == 0
        else previous_candidate_rows + max(settings.training_min_new_games, 50)
    )
    candidate = train_candidate(
        storage.load_games(),
        minimum_rows=candidate_required_rows,
    )
    candidate_created = False
    candidate_id = candidate.candidate_id
    candidate_status = candidate.status
    if candidate.status == "CANDIDATE_READY":
        if not candidate.reproducible:
            candidate_status = "BLOCKED_NOT_REPRODUCIBLE"
        else:
            candidate_created, candidate_id = storage.register_model_candidate(
                candidate.payload()
            )
            candidate_status = (
                "CANDIDATE_CREATED" if candidate_created
                else "CANDIDATE_ALREADY_REGISTERED"
            )

    registered_candidate = storage.latest_model_candidate()
    validation = validate_candidate(
        registered_candidate,
        settings=ValidationSettings(
            minimum_train_rows=settings.validation_min_train_games,
            minimum_test_rows=max(
                settings.validation_min_test_games,
                quality_policy.out_of_time_minimum_rows
                // max(1, settings.validation_min_folds),
            ),
            minimum_folds=settings.validation_min_folds,
            maximum_folds=settings.validation_max_folds,
        ),
    )
    validation_created = False
    validation_id = str(validation.get("validation_id", ""))
    if validation_id:
        validation_created, validation_id = storage.register_model_validation(
            validation
        )
    validation_status = str(validation.get("status", "WAITING_REPRODUCIBLE_CANDIDATE"))
    stored_games = storage.load_games()
    active_before_governor = storage.active_shadow_model()
    active_monitor = None
    if (
        active_before_governor
        and (
            not registered_candidate
            or active_before_governor["candidate_id"]
            != registered_candidate["candidate_id"]
        )
    ):
        active_monitor = run_autonomous_governor(
            storage,
            stored_games,
            active_before_governor,
            storage.validation_for_candidate(
                active_before_governor["candidate_id"]
            ),
            settings=GovernorSettings(
                enabled=governor_enabled,
                minimum_live_samples=max(
                    settings.live_shadow_min_samples,
                    quality_policy.live_shadow_minimum_rows,
                ),
                minimum_training_samples=quality_policy.promotion_minimum_rows,
                report_step_samples=settings.live_shadow_report_step,
                required_positive_reports=settings.live_shadow_positive_reports,
                rollback_negative_reports=settings.live_shadow_rollback_reports,
                drift_psi_limit=settings.live_shadow_drift_psi_limit,
            ),
        )
    governor = run_autonomous_governor(
        storage,
        stored_games,
        registered_candidate,
        validation,
        settings=GovernorSettings(
            enabled=governor_enabled,
            minimum_live_samples=max(
                settings.live_shadow_min_samples,
                quality_policy.live_shadow_minimum_rows,
            ),
            minimum_training_samples=quality_policy.promotion_minimum_rows,
            report_step_samples=settings.live_shadow_report_step,
            required_positive_reports=settings.live_shadow_positive_reports,
            rollback_negative_reports=settings.live_shadow_rollback_reports,
            drift_psi_limit=settings.live_shadow_drift_psi_limit,
        ),
    )
    active_shadow_model = storage.active_shadow_model()
    active_model_id = storage.active_shadow_model_id()
    active_hyperparameters = (
        dict(active_shadow_model["artifact"]["hyperparameters"])
        if active_shadow_model
        else dict(DEFAULT_HYPERPARAMETERS)
    )
    active_model_version = (
        active_model_id if active_shadow_model else MODEL_VERSION
    )

    picks_created = 0
    quotes_saved = 0
    odds_attempted = 0
    odds_failed = 0
    odds_empty_responses = 0
    odds_skipped_by_cycle_cap = 0
    features_saved = 0
    features_quarantined = 0
    market_consensus_saved = 0
    market_insufficient_books = 0
    single_book_shadow_observed = 0
    single_book_shadow_saved = 0
    multi_book_consensus_saved = 0
    for game in sorted(games, key=lambda item: (item.scheduled_at, item.game_id)):
        if game.finished or game.status.upper() not in {"NS", "NOT_STARTED", "TBD"}:
            continue
        if collection.provider_circuit_open or collection.request_budget_reached:
            odds_skipped_by_cycle_cap += 1
            continue
        if odds_attempted >= settings.maximum_odds_requests_per_cycle:
            odds_skipped_by_cycle_cap += 1
            continue
        if not storage.odds_refresh_due(
            game.game_id,
            settings.odds_refresh_hours,
            scheduled_at=game.scheduled_at,
            empty_refresh_hours=settings.empty_odds_retry_hours,
        ):
            continue
        odds_attempted += 1
        try:
            quotes = client.odds_for_game(game.game_id)
        except VolleyballRequestBudgetExhausted:
            collection.request_budget_reached = True
            collection.provider_failure_categories["REQUEST_BUDGET"] += 1
            odds_failed += 1
            continue
        except VolleyballProviderError as exc:
            odds_failed += 1
            collection.note_provider_error(exc)
            continue
        if not quotes:
            odds_empty_responses += 1
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
            if consensus.bookmaker_count == 1:
                single_book_shadow_observed += 1
                single_book_shadow_saved += int(consensus_inserted)
            market_insufficient_books += 1
            continue
        multi_book_consensus_saved += int(consensus_inserted)
        feature_observed_at = utc_now()
        training_games, source_metadata = storage.point_in_time_training_set(
            game, feature_observed_at
        )
        try:
            bundle = build_point_in_time_features(
                game,
                training_games,
                observed_at=feature_observed_at,
                model_version=active_model_version,
                source_metadata=source_metadata,
                hyperparameters=active_hyperparameters,
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
                "model_version": active_model_version,
                "runtime_version": RUNTIME_VERSION,
                "quality_policy": "volleyball_v12",
                "odds_snapshot_stage": odds_snapshot_stage(
                    game.scheduled_at,
                    quote.observed_at,
                ),
                "feature_key": feature_key,
                "feature_schema": FEATURE_SCHEMA_VERSION,
                "market_schema": MARKET_SCHEMA_VERSION,
                "market_integrity_status": "PASS",
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
                "market_average_overround": consensus.average_overround,
                "home_rating": prediction.home_rating,
                "away_rating": prediction.away_rating,
                "home_matches": prediction.home_matches,
                "away_matches": prediction.away_matches,
                "elo_probability": prediction.elo_probability,
                "set_form_probability": prediction.form_probability,
                "feature_quality": prediction.feature_quality,
                "generated_at": utc_now(),
                "real_execution_allowed": False,
            }
            picks_created += int(storage.create_shadow_pick(payload))

    game_index = {game.game_id: game for game in stored_games}
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
        "status": collection.status(odds_failed=odds_failed),
        "shadow_only": True,
        "runtime_version": RUNTIME_VERSION,
        "sport_quality_policy": quality_policy.__dict__,
        "games_received": len(games),
        "quotes_saved": quotes_saved,
        "picks_created": picks_created,
        "picks_settled": settled,
        "settlement_audited": settlement_audited,
        "settlement_mismatches": settlement_mismatches,
        "days_requested": collection.days_requested,
        "days_attempted": collection.days_attempted,
        "days_succeeded": collection.days_succeeded,
        "days_failed": collection.days_failed,
        "days_skipped_after_circuit": collection.days_skipped_after_circuit,
        "provider_circuit_open": collection.provider_circuit_open,
        "provider_failure_categories": dict(
            collection.provider_failure_categories
        ),
        "provider_retry_after_seconds": collection.provider_retry_after_seconds,
        "provider_quota_limit": collection.provider_quota_limit,
        "provider_quota_remaining": collection.provider_quota_remaining,
        "provider_date_scope_limited_days": collection.date_scope_limited_days,
        "provider_request_budget_reached": collection.request_budget_reached,
        "provider_requests_made": int(getattr(client, "requests_made", 0)),
        "provider_maximum_requests_per_cycle": settings.maximum_requests_per_cycle,
        "backfill_cursor_days": collection.backfill_cursor_days,
        "backfill_target_days": collection.backfill_target_days,
        "backfill_failed_dates": collection.backfill_failed_dates,
        "backfill_complete": collection.backfill_complete,
        "odds_attempted": odds_attempted,
        "odds_failed": odds_failed,
        "odds_empty_responses": odds_empty_responses,
        "odds_skipped_by_cycle_cap": odds_skipped_by_cycle_cap,
        "lookahead_days": settings.lookahead_days,
        "maximum_odds_requests_per_cycle": (
            settings.maximum_odds_requests_per_cycle
        ),
        "empty_odds_retry_hours": settings.empty_odds_retry_hours,
        "features_saved": features_saved,
        "features_quarantined": features_quarantined,
        "market_consensus_saved": market_consensus_saved,
        "multi_book_consensus_saved": multi_book_consensus_saved,
        "market_insufficient_books": market_insufficient_books,
        "single_book_shadow_observed": single_book_shadow_observed,
        "single_book_shadow_saved": single_book_shadow_saved,
        "single_book_training_admitted": 0,
        "single_book_picks_created": 0,
        "single_book_promotion_allowed": False,
        "clv_recorded": clv_recorded,
        "candidate_training_status": candidate_status,
        "candidate_created": candidate_created,
        "candidate_id": candidate_id,
        "candidate_dataset_rows": candidate.dataset_rows,
        "candidate_minimum_rows": candidate.minimum_rows,
        "candidate_previous_rows": previous_candidate_rows,
        "candidate_reproducible": candidate.reproducible,
        "walk_forward_status": validation_status,
        "walk_forward_validation_created": validation_created,
        "walk_forward_validation_id": validation_id,
        "walk_forward_candidate_id": str(validation.get("candidate_id", "")),
        "walk_forward_folds": int(validation.get("folds", 0)),
        "walk_forward_oos_samples": int(validation.get("oos_samples", 0)),
        "walk_forward_brier_improvement": float(
            validation.get("brier_improvement", 0.0)
        ),
        "walk_forward_log_loss_improvement": float(
            validation.get("log_loss_improvement", 0.0)
        ),
        "walk_forward_calibration_improvement": float(
            validation.get("calibration_improvement", 0.0)
        ),
        "walk_forward_positive_validation": bool(
            validation.get("positive_validation", False)
        ),
        "walk_forward_manual_approval_required": True,
        "autonomous_governor_status": str(governor.get("status", "UNKNOWN")),
        "active_shadow_monitor_status": str(
            (active_monitor or {}).get("status", "NOT_REQUIRED")
        ),
        "autonomous_governor_enabled": governor_enabled,
        "autonomous_governor_configured": settings.autonomous_governor_enabled,
        "market_integrity_v13_training_ready": integrity_training_ready,
        "live_shadow_report_status": str(
            governor.get("live_report_status", "WAITING")
        ),
        "live_shadow_settled_samples": int(
            governor.get("settled_samples", 0)
        ),
        "active_shadow_model_id": active_model_id,
        "shadow_model_changed": bool(
            governor.get("shadow_model_changed", False)
            or (active_monitor or {}).get("shadow_model_changed", False)
        ),
        "active_model_modified": bool(
            governor.get("shadow_model_changed", False)
            or (active_monitor or {}).get("shadow_model_changed", False)
        ),
        "active_model_scope": "volleyball_shadow_only",
        "automatic_model_promotion_allowed": integrity_training_ready,
        "automatic_model_promotion_scope": "volleyball_shadow_only",
        "automatic_rollback_enabled": True,
        "football_active_model_modified": False,
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
