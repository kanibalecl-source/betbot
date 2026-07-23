from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .domain import VolleyballGame, utc_now
from .features import parse_utc
from .model import VolleyballEloModel
from .training import DEFAULT_HYPERPARAMETERS, canonical_json
from .validation import _ece, _paired_ci


LIVE_REPORT_SCHEMA_VERSION = "volleyball.live_shadow_report.v1"


@dataclass(frozen=True)
class GovernorSettings:
    enabled: bool = True
    minimum_live_samples: int = 30
    report_step_samples: int = 10
    required_positive_reports: int = 3
    rollback_negative_reports: int = 3
    segment_minimum_samples: int = 10
    segment_maximum_loss_degradation: float = 0.015
    drift_psi_limit: float = 0.25
    bootstrap_samples: int = 1000


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _probability_distribution(
    probabilities: list[float],
    bins: int = 5,
) -> list[float]:
    counts = [0] * bins
    for probability in probabilities:
        counts[min(bins - 1, max(0, int(float(probability) * bins)))] += 1
    total = sum(counts)
    return [count / total for count in counts] if total else [0.0] * bins


def _psi(reference: list[float], observed: list[float]) -> float:
    reference_dist = _probability_distribution(reference)
    observed_dist = _probability_distribution(observed)
    epsilon = 1e-6
    return sum(
        (max(observed_value, epsilon) - max(reference_value, epsilon))
        * math.log(
            max(observed_value, epsilon) / max(reference_value, epsilon)
        )
        for reference_value, observed_value in zip(
            reference_dist,
            observed_dist,
        )
    )


def _training_probabilities(candidate: dict) -> list[float]:
    artifact = candidate["artifact"]
    model = VolleyballEloModel(**dict(artifact["hyperparameters"]))
    probabilities: list[float] = []
    rows = sorted(
        candidate["dataset_document"].get("rows", []),
        key=lambda item: (str(item["scheduled_at"]), str(item["game_id"])),
    )
    for row in rows:
        game = VolleyballGame(
            game_id=str(row["game_id"]),
            scheduled_at=str(row["scheduled_at"]),
            status="FT",
            league_id=str(row.get("league_id", "")),
            league_name="",
            country="",
            season=str(row.get("season", "")),
            home_team_id=str(row["home_team_id"]),
            home_team="",
            away_team_id=str(row["away_team_id"]),
            away_team="",
            home_sets=int(row["home_sets"]),
            away_sets=int(row["away_sets"]),
            raw={},
        )
        probabilities.append(
            model.predict(game.home_team_id, game.away_team_id).home_probability
        )
        model.fit([game])
    return probabilities


def _model_parameters(storage, model_id: str) -> dict:
    if model_id == "BASELINE":
        return dict(DEFAULT_HYPERPARAMETERS)
    candidate = storage.model_candidate(model_id)
    if not candidate:
        return dict(DEFAULT_HYPERPARAMETERS)
    return dict(candidate["artifact"]["hyperparameters"])


def create_live_shadow_predictions(
    storage,
    games: Iterable[VolleyballGame],
    candidate: dict,
) -> int:
    candidate_id = str(candidate["candidate_id"])
    active_id = storage.active_shadow_model_id()
    comparator_id = (
        storage.comparator_model_id(candidate_id)
        if active_id == candidate_id
        else active_id
    )
    champion_parameters = _model_parameters(storage, comparator_id)
    challenger_parameters = dict(candidate["artifact"]["hyperparameters"])
    created = 0
    for game in games:
        if game.finished or game.status.upper() not in {
            "NS",
            "NOT_STARTED",
            "TBD",
        }:
            continue
        observed_at = utc_now()
        try:
            if parse_utc(observed_at) >= parse_utc(game.scheduled_at):
                continue
        except ValueError:
            continue
        training_games, _ = storage.point_in_time_training_set(game, observed_at)
        champion = VolleyballEloModel(**champion_parameters)
        challenger = VolleyballEloModel(**challenger_parameters)
        champion.fit(training_games)
        challenger.fit(training_games)
        champion_probability = champion.predict(
            game.home_team_id,
            game.away_team_id,
        ).home_probability
        challenger_probability = challenger.predict(
            game.home_team_id,
            game.away_team_id,
        ).home_probability
        inserted, _ = storage.record_live_prediction(
            candidate_id=candidate_id,
            comparator_model_id=comparator_id,
            role="CHAMPION",
            game=game,
            observed_at=observed_at,
            home_probability=champion_probability,
            model_parameters=champion_parameters,
        )
        created += int(inserted)
        inserted, _ = storage.record_live_prediction(
            candidate_id=candidate_id,
            comparator_model_id=candidate_id,
            role="CHALLENGER",
            game=game,
            observed_at=observed_at,
            home_probability=challenger_probability,
            model_parameters=challenger_parameters,
        )
        created += int(inserted)
    return created


def build_live_shadow_report(
    storage,
    candidate: dict,
    settings: GovernorSettings,
) -> dict:
    candidate_id = str(candidate["candidate_id"])
    rows = storage.paired_live_rows(candidate_id)
    samples = len(rows)
    champion_brier = [float(row["champion_brier"]) for row in rows]
    challenger_brier = [float(row["challenger_brier"]) for row in rows]
    champion_log = [float(row["champion_log_loss"]) for row in rows]
    challenger_log = [float(row["challenger_log_loss"]) for row in rows]
    champion_probabilities = [
        float(row["champion_probability"]) for row in rows
    ]
    challenger_probabilities = [
        float(row["challenger_probability"]) for row in rows
    ]
    targets = [int(row["target"]) for row in rows]
    brier_improvement = _mean(champion_brier) - _mean(challenger_brier)
    log_improvement = _mean(champion_log) - _mean(challenger_log)
    champion_ece = _ece(champion_probabilities, targets, 10)
    challenger_ece = _ece(challenger_probabilities, targets, 10)
    seed = int(hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:16], 16)
    brier_ci = _paired_ci(
        champion_brier,
        challenger_brier,
        samples=settings.bootstrap_samples,
        seed=seed,
    )
    log_ci = _paired_ci(
        champion_log,
        challenger_log,
        samples=settings.bootstrap_samples,
        seed=seed ^ 0xD1B54A32D192ED03,
    )
    by_league: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_league[str(row.get("league_id") or "UNKNOWN")].append(index)
    segments = {}
    for league_id, indexes in sorted(by_league.items()):
        if len(indexes) < settings.segment_minimum_samples:
            continue
        champion_segment_brier = _mean(
            [champion_brier[index] for index in indexes]
        )
        challenger_segment_brier = _mean(
            [challenger_brier[index] for index in indexes]
        )
        champion_segment_log = _mean([champion_log[index] for index in indexes])
        challenger_segment_log = _mean(
            [challenger_log[index] for index in indexes]
        )
        stable = (
            challenger_segment_brier
            <= champion_segment_brier
            + settings.segment_maximum_loss_degradation
            and challenger_segment_log
            <= champion_segment_log
            + settings.segment_maximum_loss_degradation
        )
        segments[league_id] = {
            "samples": len(indexes),
            "brier_improvement": round(
                champion_segment_brier - challenger_segment_brier,
                10,
            ),
            "log_loss_improvement": round(
                champion_segment_log - challenger_segment_log,
                10,
            ),
            "stable": stable,
        }
    segment_stability = all(item["stable"] for item in segments.values())
    training_probabilities = _training_probabilities(candidate)
    psi = (
        _psi(training_probabilities, challenger_probabilities)
        if samples >= settings.minimum_live_samples
        else 0.0
    )
    drift_status = (
        "WAITING_SAMPLE"
        if samples < settings.minimum_live_samples
        else ("PASS" if psi <= settings.drift_psi_limit else "CRITICAL")
    )
    gates = {
        "minimum_live_samples": samples >= settings.minimum_live_samples,
        "brier_improvement_ci_positive": (
            brier_improvement > 0 and brier_ci[0] > 0
        ),
        "log_loss_improvement_ci_positive": (
            log_improvement > 0 and log_ci[0] > 0
        ),
        "calibration_not_degraded": challenger_ece <= champion_ece,
        "segment_stability": segment_stability,
        "no_critical_probability_drift": drift_status != "CRITICAL",
    }
    positive = all(gates.values())
    status = (
        "COLLECTING_LIVE_SHADOW"
        if samples < settings.minimum_live_samples
        else (
            "POSITIVE_LIVE_SHADOW"
            if positive
            else "NEGATIVE_LIVE_SHADOW"
        )
    )
    report = {
        "report_schema": LIVE_REPORT_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "comparator_model_id": (
            str(rows[-1].get("comparator_model_id", ""))
            if rows
            else storage.comparator_model_id(candidate_id)
        ),
        "settled_samples": samples,
        "status": status,
        "positive": positive,
        "champion_brier": round(_mean(champion_brier), 10),
        "challenger_brier": round(_mean(challenger_brier), 10),
        "brier_improvement": round(brier_improvement, 10),
        "brier_improvement_ci95": brier_ci,
        "champion_log_loss": round(_mean(champion_log), 10),
        "challenger_log_loss": round(_mean(challenger_log), 10),
        "log_loss_improvement": round(log_improvement, 10),
        "log_loss_improvement_ci95": log_ci,
        "champion_calibration_error": round(champion_ece, 10),
        "challenger_calibration_error": round(challenger_ece, 10),
        "calibration_improvement": round(champion_ece - challenger_ece, 10),
        "league_segments": segments,
        "probability_drift_psi": round(psi, 10),
        "drift_status": drift_status,
        "gates": gates,
        "shadow_only": True,
        "real_execution_allowed": False,
        "football_model_modified": False,
    }
    report_sha = hashlib.sha256(
        canonical_json(report).encode("utf-8")
    ).hexdigest()
    return {
        **report,
        "report_sha256": report_sha,
        "report_id": f"volleyball_live_report_{report_sha[:24]}",
        "report_created": False,
    }


def run_autonomous_governor(
    storage,
    games: Iterable[VolleyballGame],
    candidate: dict | None,
    validation: dict | None,
    *,
    settings: GovernorSettings | None = None,
) -> dict:
    selected = settings or GovernorSettings()
    if not selected.enabled:
        return {
            "status": "DISABLED",
            "shadow_model_changed": False,
            "real_execution_allowed": False,
        }
    if not candidate:
        return {
            "status": "WAITING_REPRODUCIBLE_CANDIDATE",
            "shadow_model_changed": False,
            "real_execution_allowed": False,
        }
    candidate_id = str(candidate["candidate_id"])
    if not validation or validation.get("status") != (
        "POSITIVE_VALIDATION_MANUAL_APPROVAL"
    ):
        return {
            "status": "WAITING_POSITIVE_WALK_FORWARD",
            "candidate_id": candidate_id,
            "shadow_model_changed": False,
            "real_execution_allowed": False,
        }

    all_games = list(games)
    predictions_created = create_live_shadow_predictions(
        storage,
        all_games,
        candidate,
    )
    predictions_settled = storage.settle_live_predictions(all_games)
    report = build_live_shadow_report(storage, candidate, selected)
    last_samples = storage.latest_live_report_samples(candidate_id)
    report_created = False
    report_id = str(report["report_id"])
    if (
        int(report["settled_samples"]) >= selected.minimum_live_samples
        and int(report["settled_samples"])
        >= last_samples + selected.report_step_samples
    ):
        report_created, report_id = storage.register_live_report(report)

    active_id = storage.active_shadow_model_id()
    recent_positive = storage.recent_live_report_statuses(
        candidate_id,
        selected.required_positive_reports,
    )
    recent_negative = storage.recent_live_report_statuses(
        candidate_id,
        selected.rollback_negative_reports,
    )
    if active_id == candidate_id:
        if (
            len(recent_negative) >= selected.rollback_negative_reports
            and all(status == "NEGATIVE_LIVE_SHADOW" for status in recent_negative)
        ):
            target = storage.comparator_model_id(candidate_id)
            changed, event_id = storage.record_lifecycle_event(
                candidate_id=candidate_id,
                event_type="ROLLED_BACK_SHADOW",
                previous_model_id=target,
                evidence_report_id=report_id,
                reason="consecutive_negative_live_shadow_or_drift",
            )
            return {
                "status": "ROLLED_BACK_SHADOW" if changed else "ROLLBACK_ALREADY_RECORDED",
                "candidate_id": candidate_id,
                "active_shadow_model_id": storage.active_shadow_model_id(),
                "lifecycle_event_id": event_id,
                "shadow_model_changed": changed,
                "predictions_created": predictions_created,
                "predictions_settled": predictions_settled,
                "live_report_status": report["status"],
                "live_report_created": report_created,
                "real_execution_allowed": False,
            }
        return {
            "status": "ACTIVE_SHADOW_MONITORING",
            "candidate_id": candidate_id,
            "active_shadow_model_id": active_id,
            "shadow_model_changed": False,
            "predictions_created": predictions_created,
            "predictions_settled": predictions_settled,
            "live_report_status": report["status"],
            "live_report_created": report_created,
            "settled_samples": report["settled_samples"],
            "real_execution_allowed": False,
        }

    if (
        len(recent_positive) >= selected.required_positive_reports
        and all(status == "POSITIVE_LIVE_SHADOW" for status in recent_positive)
    ):
        changed, event_id = storage.record_lifecycle_event(
            candidate_id=candidate_id,
            event_type="PROMOTED_SHADOW",
            previous_model_id=active_id,
            evidence_report_id=report_id,
            reason="walk_forward_and_repeated_live_shadow_positive",
        )
        return {
            "status": "PROMOTED_SHADOW" if changed else "PROMOTION_ALREADY_RECORDED",
            "candidate_id": candidate_id,
            "active_shadow_model_id": storage.active_shadow_model_id(),
            "lifecycle_event_id": event_id,
            "shadow_model_changed": changed,
            "predictions_created": predictions_created,
            "predictions_settled": predictions_settled,
            "live_report_status": report["status"],
            "live_report_created": report_created,
            "real_execution_allowed": False,
        }

    return {
        "status": (
            "COLLECTING_LIVE_SHADOW"
            if report["status"] == "COLLECTING_LIVE_SHADOW"
            else "WAITING_REPEATED_POSITIVE_LIVE_REPORTS"
        ),
        "candidate_id": candidate_id,
        "active_shadow_model_id": active_id,
        "shadow_model_changed": False,
        "predictions_created": predictions_created,
        "predictions_settled": predictions_settled,
        "live_report_status": report["status"],
        "live_report_created": report_created,
        "settled_samples": report["settled_samples"],
        "positive_reports_required": selected.required_positive_reports,
        "recent_positive_reports": sum(
            status == "POSITIVE_LIVE_SHADOW" for status in recent_positive
        ),
        "real_execution_allowed": False,
    }
