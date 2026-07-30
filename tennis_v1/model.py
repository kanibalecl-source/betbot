from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from .domain import TennisMatch


BASELINE_WEIGHTS = {"surface": 0.70, "general": 0.30}
SURFACES = {"hard", "clay", "grass", "carpet", "indoor", "unknown"}


def normalized_surface(value: str) -> str:
    raw = str(value or "unknown").lower()
    for name in SURFACES:
        if name in raw:
            return name
    return "unknown"


def elo_probability(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def _clamp_probability(value: float) -> float:
    return min(0.995, max(0.005, float(value)))


def _log_loss(probability: float, outcome: int) -> float:
    probability = _clamp_probability(probability)
    return -(
        outcome * math.log(probability)
        + (1 - outcome) * math.log(1.0 - probability)
    )


@dataclass
class Ratings:
    general: dict[str, float]
    surface: dict[tuple[str, str], float]
    matches: Counter[str]


def build_ratings(matches: Iterable[TennisMatch]) -> Ratings:
    general: dict[str, float] = defaultdict(lambda: 1500.0)
    surface: dict[tuple[str, str], float] = defaultdict(lambda: 1500.0)
    counts: Counter[str] = Counter()
    for match in sorted(matches, key=lambda item: (item.scheduled_at, item.event_id)):
        if not match.finished or match.void:
            continue
        key1 = (match.player1_id, normalized_surface(match.surface))
        key2 = (match.player2_id, normalized_surface(match.surface))
        surface_p = elo_probability(surface[key1], surface[key2])
        general_p = elo_probability(
            general[match.player1_id], general[match.player2_id]
        )
        outcome = 1.0 if match.winner_id == match.player1_id else 0.0
        experience = min(counts[match.player1_id], counts[match.player2_id])
        k_factor = 40.0 if experience < 20 else 24.0
        general_delta = k_factor * (outcome - general_p)
        surface_delta = (k_factor + 4.0) * (outcome - surface_p)
        general[match.player1_id] += general_delta
        general[match.player2_id] -= general_delta
        surface[key1] += surface_delta
        surface[key2] -= surface_delta
        counts[match.player1_id] += 1
        counts[match.player2_id] += 1
    return Ratings(dict(general), dict(surface), counts)


def predict_match(
    match: TennisMatch,
    ratings: Ratings,
    weights: dict[str, float] | None = None,
) -> dict[str, float]:
    chosen = weights or BASELINE_WEIGHTS
    surface_name = normalized_surface(match.surface)
    p_surface = elo_probability(
        ratings.surface.get((match.player1_id, surface_name), 1500.0),
        ratings.surface.get((match.player2_id, surface_name), 1500.0),
    )
    p_general = elo_probability(
        ratings.general.get(match.player1_id, 1500.0),
        ratings.general.get(match.player2_id, 1500.0),
    )
    surface_weight = float(chosen.get("surface", 0.70))
    general_weight = float(chosen.get("general", 1.0 - surface_weight))
    total = max(0.001, surface_weight + general_weight)
    probability = _clamp_probability(
        (surface_weight * p_surface + general_weight * p_general) / total
    )
    experience = min(
        ratings.matches.get(match.player1_id, 0),
        ratings.matches.get(match.player2_id, 0),
    )
    feature_quality = min(1.0, experience / 30.0)
    confidence = min(
        0.95,
        0.50 + abs(probability - 0.50) * 0.80 + feature_quality * 0.08,
    )
    return {
        "player1_probability": probability,
        "player2_probability": 1.0 - probability,
        "confidence": confidence,
        "feature_quality": feature_quality,
        "surface_probability": p_surface,
        "general_probability": p_general,
    }


def _sequential_predictions(
    matches: list[TennisMatch],
    weights: dict[str, float],
) -> list[dict[str, Any]]:
    general: dict[str, float] = defaultdict(lambda: 1500.0)
    surface: dict[tuple[str, str], float] = defaultdict(lambda: 1500.0)
    counts: Counter[str] = Counter()
    output: list[dict[str, Any]] = []
    for match in sorted(matches, key=lambda item: (item.scheduled_at, item.event_id)):
        if not match.finished or match.void:
            continue
        surface_name = normalized_surface(match.surface)
        key1 = (match.player1_id, surface_name)
        key2 = (match.player2_id, surface_name)
        p_surface = elo_probability(surface[key1], surface[key2])
        p_general = elo_probability(
            general[match.player1_id], general[match.player2_id]
        )
        p = _clamp_probability(
            float(weights["surface"]) * p_surface
            + float(weights["general"]) * p_general
        )
        y = 1 if match.winner_id == match.player1_id else 0
        output.append(
            {
                "event_id": match.event_id,
                "scheduled_at": match.scheduled_at,
                "surface": surface_name,
                "probability": p,
                "outcome": y,
            }
        )
        experience = min(counts[match.player1_id], counts[match.player2_id])
        k_factor = 40.0 if experience < 20 else 24.0
        general_delta = k_factor * (y - p_general)
        surface_delta = (k_factor + 4.0) * (y - p_surface)
        general[match.player1_id] += general_delta
        general[match.player2_id] -= general_delta
        surface[key1] += surface_delta
        surface[key2] -= surface_delta
        counts[match.player1_id] += 1
        counts[match.player2_id] += 1
    return output


def validate_candidates(
    matches: list[TennisMatch],
    *,
    minimum_rows: int,
    minimum_surface_rows: int,
    test_rows: int,
    minimum_folds: int,
    minimum_brier_improvement: float,
) -> dict[str, Any]:
    admitted = [match for match in matches if match.finished and not match.void]
    surface_rows = Counter(normalized_surface(match.surface) for match in admitted)
    required_surfaces = [
        surface for surface in ("hard", "clay", "grass")
        if surface_rows.get(surface, 0)
    ]
    if len(admitted) < minimum_rows:
        return {
            "status": "WAITING_MINIMUM_SAMPLE",
            "dataset_rows": len(admitted),
            "surface_rows": dict(surface_rows),
            "minimum_rows": minimum_rows,
        }
    if any(surface_rows[surface] < minimum_surface_rows for surface in required_surfaces):
        return {
            "status": "WAITING_SURFACE_SAMPLES",
            "dataset_rows": len(admitted),
            "surface_rows": dict(surface_rows),
            "minimum_surface_rows": minimum_surface_rows,
        }
    candidates = [
        {"surface": round(value, 2), "general": round(1.0 - value, 2)}
        for value in (0.50, 0.60, 0.70, 0.80, 0.90)
    ]
    all_predictions = {
        json.dumps(weights, sort_keys=True): _sequential_predictions(
            admitted, weights
        )
        for weights in [BASELINE_WEIGHTS, *candidates]
    }
    baseline_key = json.dumps(BASELINE_WEIGHTS, sort_keys=True)
    baseline = all_predictions[baseline_key]
    available_folds = max(0, (len(baseline) - minimum_rows // 2) // test_rows)
    folds = min(6, available_folds)
    if folds < minimum_folds:
        return {
            "status": "WAITING_WALK_FORWARD",
            "dataset_rows": len(admitted),
            "surface_rows": dict(surface_rows),
            "folds": folds,
            "minimum_folds": minimum_folds,
        }
    start = len(baseline) - folds * test_rows
    baseline_slices = [
        baseline[start + fold * test_rows:start + (fold + 1) * test_rows]
        for fold in range(folds)
    ]
    best: dict[str, Any] | None = None
    for weights in candidates:
        key = json.dumps(weights, sort_keys=True)
        rows = all_predictions[key]
        candidate_slices = [
            rows[start + fold * test_rows:start + (fold + 1) * test_rows]
            for fold in range(folds)
        ]
        fold_results = []
        for champion_rows, challenger_rows in zip(
            baseline_slices, candidate_slices
        ):
            champion_brier = sum(
                (row["probability"] - row["outcome"]) ** 2
                for row in champion_rows
            ) / len(champion_rows)
            challenger_brier = sum(
                (row["probability"] - row["outcome"]) ** 2
                for row in challenger_rows
            ) / len(challenger_rows)
            champion_log = sum(
                _log_loss(row["probability"], row["outcome"])
                for row in champion_rows
            ) / len(champion_rows)
            challenger_log = sum(
                _log_loss(row["probability"], row["outcome"])
                for row in challenger_rows
            ) / len(challenger_rows)
            fold_results.append(
                {
                    "brier_improvement": champion_brier - challenger_brier,
                    "log_loss_improvement": champion_log - challenger_log,
                    "positive": (
                        challenger_brier < champion_brier
                        and challenger_log <= champion_log
                    ),
                }
            )
        result = {
            "weights": weights,
            "folds": folds,
            "positive_folds": sum(
                1 for item in fold_results if item["positive"]
            ),
            "brier_improvement": sum(
                item["brier_improvement"] for item in fold_results
            ) / folds,
            "log_loss_improvement": sum(
                item["log_loss_improvement"] for item in fold_results
            ) / folds,
            "fold_results": fold_results,
        }
        if best is None or result["brier_improvement"] > best["brier_improvement"]:
            best = result
    assert best is not None
    positive = (
        best["positive_folds"] >= minimum_folds
        and best["brier_improvement"] >= minimum_brier_improvement
        and best["log_loss_improvement"] > 0.0
    )
    best.update(
        {
            "status": "POSITIVE" if positive else "REJECTED_OR_REVIEW",
            "dataset_rows": len(admitted),
            "surface_rows": dict(surface_rows),
            "reproducible": True,
        }
    )
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "rows": [
                    (match.event_id, match.scheduled_at, match.winner_id)
                    for match in admitted
                ],
                "weights": best["weights"],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:24]
    best["candidate_id"] = f"tennis_candidate_{fingerprint}"
    best["validation_id"] = f"tennis_validation_{fingerprint}"
    return best

