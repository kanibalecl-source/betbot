from __future__ import annotations

import hashlib
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .domain import VolleyballGame
from .model import VolleyballEloModel
from .training import DEFAULT_HYPERPARAMETERS, canonical_json


VALIDATION_SCHEMA_VERSION = "volleyball.walk_forward_validation.v1"
VALIDATION_METHOD = "expanding_window_walk_forward"


@dataclass(frozen=True)
class ValidationSettings:
    minimum_train_rows: int = 40
    minimum_test_rows: int = 20
    minimum_folds: int = 3
    maximum_folds: int = 5
    bootstrap_samples: int = 1000
    calibration_bins: int = 10


def _game_from_row(row: dict) -> VolleyballGame:
    return VolleyballGame(
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


def _ordered_games(dataset_document: dict) -> list[VolleyballGame]:
    games = [_game_from_row(row) for row in dataset_document.get("rows", [])]
    return sorted(games, key=lambda item: (item.scheduled_at, item.game_id))


def _boundaries(games: list[VolleyballGame]) -> list[int]:
    result = [0]
    for index in range(1, len(games)):
        if games[index - 1].scheduled_at != games[index].scheduled_at:
            result.append(index)
    result.append(len(games))
    return result


def build_walk_forward_folds(
    games: Iterable[VolleyballGame],
    settings: ValidationSettings,
) -> list[tuple[list[VolleyballGame], list[VolleyballGame]]]:
    ordered = sorted(games, key=lambda item: (item.scheduled_at, item.game_id))
    boundaries = _boundaries(ordered)
    train_end = next(
        (value for value in boundaries if value >= settings.minimum_train_rows),
        len(ordered),
    )
    folds: list[tuple[list[VolleyballGame], list[VolleyballGame]]] = []
    while train_end < len(ordered) and len(folds) < settings.maximum_folds:
        test_end = next(
            (
                value
                for value in boundaries
                if value >= train_end + settings.minimum_test_rows
            ),
            len(ordered),
        )
        if test_end - train_end < settings.minimum_test_rows:
            break
        folds.append((ordered[:train_end], ordered[train_end:test_end]))
        train_end = test_end
    return folds


def _clip(probability: float) -> float:
    return min(1.0 - 1e-12, max(1e-12, float(probability)))


def _losses(
    probabilities: list[float],
    targets: list[int],
) -> tuple[list[float], list[float]]:
    brier = [
        (probability - target) ** 2
        for probability, target in zip(probabilities, targets)
    ]
    log_loss = [
        -(
            target * math.log(_clip(probability))
            + (1 - target) * math.log(_clip(1.0 - probability))
        )
        for probability, target in zip(probabilities, targets)
    ]
    return brier, log_loss


def _ece(
    probabilities: list[float],
    targets: list[int],
    bins: int,
) -> float:
    if not probabilities:
        return 0.0
    buckets: dict[int, list[tuple[float, int]]] = defaultdict(list)
    for probability, target in zip(probabilities, targets):
        bucket = min(bins - 1, int(_clip(probability) * bins))
        buckets[bucket].append((probability, target))
    total = len(probabilities)
    return sum(
        len(values)
        / total
        * abs(
            sum(item[0] for item in values) / len(values)
            - sum(item[1] for item in values) / len(values)
        )
        for values in buckets.values()
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _paired_ci(
    champion_losses: list[float],
    challenger_losses: list[float],
    *,
    samples: int,
    seed: int,
) -> list[float]:
    differences = [
        champion - challenger
        for champion, challenger in zip(champion_losses, challenger_losses)
    ]
    if not differences:
        return [0.0, 0.0]
    generator = random.Random(seed)
    size = len(differences)
    means = sorted(
        _mean([differences[generator.randrange(size)] for _ in range(size)])
        for _ in range(max(100, samples))
    )
    lower = means[int(0.025 * (len(means) - 1))]
    upper = means[int(0.975 * (len(means) - 1))]
    return [round(lower, 10), round(upper, 10)]


def _score_fold(
    training: list[VolleyballGame],
    testing: list[VolleyballGame],
    *,
    challenger_parameters: dict,
) -> dict:
    champion = VolleyballEloModel(**DEFAULT_HYPERPARAMETERS)
    challenger = VolleyballEloModel(**challenger_parameters)
    champion.fit(training)
    challenger.fit(training)
    champion_probabilities: list[float] = []
    challenger_probabilities: list[float] = []
    targets: list[int] = []
    for game in testing:
        champion_probabilities.append(
            champion.predict(
                game.home_team_id,
                game.away_team_id,
            ).home_probability
        )
        challenger_probabilities.append(
            challenger.predict(
                game.home_team_id,
                game.away_team_id,
            ).home_probability
        )
        targets.append(1 if int(game.home_sets or 0) > int(game.away_sets or 0) else 0)
        # Online updates are time-safe: the result is learned only after both
        # models have emitted the probability for this match.
        champion.fit([game])
        challenger.fit([game])
    champion_brier, champion_log = _losses(champion_probabilities, targets)
    challenger_brier, challenger_log = _losses(challenger_probabilities, targets)
    return {
        "train_samples": len(training),
        "test_samples": len(testing),
        "train_end_timestamp": training[-1].scheduled_at,
        "test_start_timestamp": testing[0].scheduled_at,
        "test_end_timestamp": testing[-1].scheduled_at,
        "time_safe": training[-1].scheduled_at < testing[0].scheduled_at,
        "targets": targets,
        "champion_probabilities": champion_probabilities,
        "challenger_probabilities": challenger_probabilities,
        "champion_brier_losses": champion_brier,
        "challenger_brier_losses": challenger_brier,
        "champion_log_losses": champion_log,
        "challenger_log_losses": challenger_log,
    }


def validate_candidate(
    candidate: dict | None,
    *,
    settings: ValidationSettings | None = None,
) -> dict:
    selected = settings or ValidationSettings()
    if not candidate:
        return {
            "status": "WAITING_REPRODUCIBLE_CANDIDATE",
            "validation_created": False,
            "automatic_promotion": False,
            "manual_approval_required": True,
            "active_model_modified": False,
        }
    dataset = candidate.get("dataset_document")
    artifact = candidate.get("artifact")
    candidate_id = str(candidate.get("candidate_id", ""))
    if (
        not candidate_id
        or not isinstance(dataset, dict)
        or not isinstance(artifact, dict)
        or candidate.get("reproducible") is not True
    ):
        return {
            "status": "BLOCKED_INVALID_CANDIDATE",
            "candidate_id": candidate_id,
            "validation_created": False,
            "automatic_promotion": False,
            "manual_approval_required": True,
            "active_model_modified": False,
        }

    games = _ordered_games(dataset)
    folds = build_walk_forward_folds(games, selected)
    fold_reports = [
        _score_fold(
            training,
            testing,
            challenger_parameters=dict(artifact["hyperparameters"]),
        )
        for training, testing in folds
    ]
    enough_data = len(fold_reports) >= selected.minimum_folds
    all_time_safe = bool(fold_reports) and all(
        report["time_safe"] for report in fold_reports
    )
    champion_probabilities = [
        probability
        for report in fold_reports
        for probability in report["champion_probabilities"]
    ]
    challenger_probabilities = [
        probability
        for report in fold_reports
        for probability in report["challenger_probabilities"]
    ]
    targets = [
        target for report in fold_reports for target in report["targets"]
    ]
    champion_brier = [
        value
        for report in fold_reports
        for value in report["champion_brier_losses"]
    ]
    challenger_brier = [
        value
        for report in fold_reports
        for value in report["challenger_brier_losses"]
    ]
    champion_log = [
        value
        for report in fold_reports
        for value in report["champion_log_losses"]
    ]
    challenger_log = [
        value
        for report in fold_reports
        for value in report["challenger_log_losses"]
    ]
    seed = int(hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:16], 16)
    brier_improvement = _mean(champion_brier) - _mean(challenger_brier)
    log_improvement = _mean(champion_log) - _mean(challenger_log)
    champion_ece = _ece(
        champion_probabilities,
        targets,
        selected.calibration_bins,
    )
    challenger_ece = _ece(
        challenger_probabilities,
        targets,
        selected.calibration_bins,
    )
    brier_ci = _paired_ci(
        champion_brier,
        challenger_brier,
        samples=selected.bootstrap_samples,
        seed=seed,
    )
    log_ci = _paired_ci(
        champion_log,
        challenger_log,
        samples=selected.bootstrap_samples,
        seed=seed ^ 0x9E3779B97F4A7C15,
    )
    gates = {
        "enough_out_of_sample_folds": enough_data,
        "chronological_no_leakage": all_time_safe,
        "brier_improvement_ci_positive": brier_improvement > 0 and brier_ci[0] > 0,
        "log_loss_improvement_ci_positive": log_improvement > 0 and log_ci[0] > 0,
        "calibration_not_degraded": challenger_ece <= champion_ece,
        "candidate_reproducible": True,
    }
    positive = all(gates.values())
    status = (
        "NO_ENOUGH_DATA"
        if not enough_data
        else (
            "POSITIVE_VALIDATION_MANUAL_APPROVAL"
            if positive
            else "REJECTED_OR_REVIEW"
        )
    )
    public_folds = [
        {
            key: report[key]
            for key in (
                "train_samples",
                "test_samples",
                "train_end_timestamp",
                "test_start_timestamp",
                "test_end_timestamp",
                "time_safe",
            )
        }
        | {
            "champion_brier": round(_mean(report["champion_brier_losses"]), 10),
            "challenger_brier": round(_mean(report["challenger_brier_losses"]), 10),
            "champion_log_loss": round(_mean(report["champion_log_losses"]), 10),
            "challenger_log_loss": round(_mean(report["challenger_log_losses"]), 10),
        }
        for report in fold_reports
    ]
    report = {
        "validation_schema": VALIDATION_SCHEMA_VERSION,
        "method": VALIDATION_METHOD,
        "sport": "volleyball",
        "candidate_id": candidate_id,
        "candidate_artifact_sha256": str(candidate.get("artifact_sha256", "")),
        "dataset_sha256": str(candidate.get("dataset_sha256", "")),
        "dataset_rows": len(games),
        "folds": len(fold_reports),
        "oos_samples": len(targets),
        "chronological_order": True,
        "online_updates_after_prediction_only": True,
        "champion": {
            "algorithm": "chronological_elo",
            "hyperparameters": dict(DEFAULT_HYPERPARAMETERS),
            "brier": round(_mean(champion_brier), 10),
            "log_loss": round(_mean(champion_log), 10),
            "calibration_error": round(champion_ece, 10),
        },
        "challenger": {
            "algorithm": str(artifact.get("algorithm", "")),
            "hyperparameters": dict(artifact["hyperparameters"]),
            "brier": round(_mean(challenger_brier), 10),
            "log_loss": round(_mean(challenger_log), 10),
            "calibration_error": round(challenger_ece, 10),
        },
        "brier_improvement": round(brier_improvement, 10),
        "brier_improvement_ci95": brier_ci,
        "log_loss_improvement": round(log_improvement, 10),
        "log_loss_improvement_ci95": log_ci,
        "calibration_improvement": round(champion_ece - challenger_ece, 10),
        "fold_details": public_folds,
        "gates": gates,
        "status": status,
        "positive_validation": positive,
        "automatic_promotion": False,
        "manual_approval_required": True,
        "active_model_modified": False,
        "real_execution_allowed": False,
    }
    report_sha256 = hashlib.sha256(
        canonical_json(report).encode("utf-8")
    ).hexdigest()
    return {
        **report,
        "report_sha256": report_sha256,
        "validation_id": f"volleyball_validation_{report_sha256[:24]}",
        "validation_created": False,
    }
