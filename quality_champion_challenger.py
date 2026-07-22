"""Leakage-safe Champion-Challenger walk-forward validation.

The validator is deliberately read-only with respect to the active model.  A
fresh challenger is fitted on every expanding training window and evaluated
only on the chronologically later test window.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from statistics import NormalDist
from typing import Any, Iterable, Mapping, Sequence

from quality_upgrade_engine import (
    BetaCalibrator,
    probability_drift_report,
    train_time_safe_state,
)

MODEL_NAMES = ("current", "dixon_coles", "market")


def _target(row: Mapping[str, Any]) -> int | None:
    value = str(row.get("target", "")).strip().upper()
    if value in {"1", "TRUE", "WON", "WIN"}:
        return 1
    if value in {"0", "FALSE", "LOST", "LOSS"}:
        return 0
    return None


def _number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _clean_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    keys = ("current_probability", "dixon_coles_probability", "market_probability")
    for position, row in enumerate(rows):
        target = _target(row)
        values = [_number(row.get(key)) for key in keys]
        if target is None or any(value is None for value in values):
            continue
        clean.append({
            "position": position,
            "fixture_id": str(row.get("fixture_id", "") or ""),
            "timestamp": str(row.get("timestamp", "")),
            "market": str(row.get("market", "UNKNOWN") or "UNKNOWN"),
            "league": str(row.get("league", "UNKNOWN") or "UNKNOWN"),
            "source": str(row.get("source", "UNKNOWN") or "UNKNOWN"),
            "values": [max(1e-5, min(1.0 - 1e-5, float(value))) for value in values],
            "target": target,
            "odds": _number(row.get("odds")),
            "closing_odds": _number(row.get("closing_odds")),
        })
    return clean


def train_candidate_state(
    rows: Iterable[Mapping[str, Any]],
    min_segment_samples: int = 500,
    max_segments: int = 12,
) -> dict[str, Any]:
    """Train global state plus sufficiently large market/league segments."""
    source_rows = list(rows)
    state = train_time_safe_state(source_rows)
    if state.get("status") != "TRAINED_TIME_SAFE":
        return state
    segments: dict[str, Any] = {}
    eligible: list[tuple[int, str, str, list[Mapping[str, Any]]]] = []
    for field in ("market", "league"):
        values = sorted({str(row.get(field, "") or "") for row in source_rows} - {"", "UNKNOWN"})
        for value in values:
            subset = [row for row in source_rows if str(row.get(field, "") or "") == value]
            if len(subset) < max(30, int(min_segment_samples)):
                continue
            eligible.append((len(subset), field, value, subset))
    for _, field, value, subset in sorted(eligible, reverse=True)[:max(0, int(max_segments))]:
        trained = train_time_safe_state(subset)
        if trained.get("status") == "TRAINED_TIME_SAFE":
            segments[f"{field}::{value}"] = trained
    return {
        **state,
        "segment_models": segments,
        "segment_minimum_samples": max(30, int(min_segment_samples)),
        "segment_maximum_count": max(0, int(max_segments)),
        "segment_fallback": "global",
    }


def _state_predict(
    values: Sequence[float],
    state: Mapping[str, Any] | None,
    market: str = "",
    league: str = "",
) -> float:
    if not state:
        return float(values[0])
    segments = state.get("segment_models", {})
    if isinstance(segments, Mapping):
        selected = segments.get(f"market::{market}") or segments.get(f"league::{league}")
        if isinstance(selected, Mapping):
            state = selected
    configured = state.get("stacking_weights", {})
    configured = configured if isinstance(configured, Mapping) else {}
    defaults = (0.45, 0.35, 0.20)
    weights = []
    for name, default in zip(MODEL_NAMES, defaults):
        value = _number(configured.get(name))
        weights.append(max(0.0, default if value is None else value))
    total = sum(weights) or 1.0
    mixture = sum(value * weight for value, weight in zip(values, weights)) / total
    beta = state.get("beta_calibration", {})
    beta = beta if isinstance(beta, Mapping) else {}
    a = _number(beta.get("a"))
    b = _number(beta.get("b"))
    c = _number(beta.get("c"))
    return BetaCalibrator(
        1.0 if a is None else a,
        1.0 if b is None else b,
        0.0 if c is None else c,
    ).predict(mixture)


def _ece(probabilities: Sequence[float], targets: Sequence[int], bins: int = 10) -> float:
    error = 0.0
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        members = [
            pos for pos, probability in enumerate(probabilities)
            if low <= probability < high or (index == bins - 1 and probability == 1.0)
        ]
        if not members:
            continue
        confidence = sum(probabilities[pos] for pos in members) / len(members)
        frequency = sum(targets[pos] for pos in members) / len(members)
        error += len(members) / len(targets) * abs(confidence - frequency)
    return error


def _bet_metrics(
    probabilities: Sequence[float],
    targets: Sequence[int],
    odds: Sequence[float | None],
    closing_odds: Sequence[float | None],
    min_edge: float,
) -> dict[str, Any]:
    profits: list[float] = []
    clv: list[float] = []
    for probability, target, decimal, closing in zip(
        probabilities, targets, odds, closing_odds
    ):
        if decimal is None or decimal <= 1.0 or probability * decimal - 1.0 < min_edge:
            continue
        profits.append(decimal - 1.0 if target else -1.0)
        if closing is not None and closing > 1.0:
            clv.append(decimal / closing - 1.0)
    equity = peak = drawdown = 0.0
    for profit in profits:
        equity += profit
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return {
        "bets": len(profits),
        "coverage": round(len(profits) / max(1, len(targets)), 6),
        "profit_units": round(sum(profits), 6),
        "yield": round(sum(profits) / max(1, len(profits)), 6),
        "max_drawdown_units": round(drawdown, 6),
        "clv_samples": len(clv),
        "mean_clv": round(sum(clv) / max(1, len(clv)), 6),
    }


def _metrics(
    probabilities: Sequence[float],
    targets: Sequence[int],
    odds: Sequence[float | None],
    closing_odds: Sequence[float | None],
    min_edge: float,
) -> dict[str, Any]:
    if not targets:
        return {"samples": 0, "brier_score": 1.0, "log_loss": 99.0}
    brier = sum((p - y) ** 2 for p, y in zip(probabilities, targets)) / len(targets)
    log_loss = -sum(
        y * math.log(max(1e-8, p)) + (1 - y) * math.log(max(1e-8, 1 - p))
        for p, y in zip(probabilities, targets)
    ) / len(targets)
    accuracy = sum((p >= 0.5) == bool(y) for p, y in zip(probabilities, targets)) / len(targets)
    return {
        "samples": len(targets),
        "brier_score": round(brier, 8),
        "log_loss": round(log_loss, 8),
        "calibration_error": round(_ece(probabilities, targets), 8),
        "accuracy": round(accuracy, 6),
        **_bet_metrics(probabilities, targets, odds, closing_odds, min_edge),
    }


def _paired_ci(values: Sequence[float], confidence: float = 0.95) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "lower": 0.0, "upper": 0.0, "confidence": confidence}
    mean = sum(values) / len(values)
    if len(values) == 1:
        margin = 0.0
    else:
        variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
        z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
        margin = z * math.sqrt(variance / len(values))
    return {
        "mean": round(mean, 8),
        "lower": round(mean - margin, 8),
        "upper": round(mean + margin, 8),
        "confidence": confidence,
    }


def _slice_report(records: Sequence[dict[str, Any]], field: str, min_samples: int) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[str(record[field])].append(record)
    output: dict[str, Any] = {}
    stable = total = 0
    for name, group in groups.items():
        if len(group) < min_samples:
            continue
        total += 1
        champion_brier = sum(item["champion_brier"] for item in group) / len(group)
        challenger_brier = sum(item["challenger_brier"] for item in group) / len(group)
        gain = champion_brier - challenger_brier
        if gain >= -0.002:
            stable += 1
        output[name] = {
            "samples": len(group),
            "brier_improvement": round(gain, 8),
            "non_degrading": gain >= -0.002,
        }
    return {
        "eligible_slices": total,
        "non_degrading_slices": stable,
        "non_degrading_ratio": round(stable / max(1, total), 6),
        "details": output,
    }


def walk_forward_validate(
    rows: Iterable[Mapping[str, Any]],
    champion: Mapping[str, Any] | None,
    *,
    min_brier_improvement: float = 0.0002,
    min_log_loss_improvement: float = 0.0002,
    min_test_samples: int = 300,
    min_folds: int = 4,
    min_edge: float = 0.02,
) -> dict[str, Any]:
    """Compare fold-trained challengers with a frozen champion on future rows."""
    clean = sorted(
        _clean_rows(rows),
        key=lambda item: (item["timestamp"], item["position"]),
    )
    sample_count = len(clean)
    if sample_count < 60:
        return {
            "status": "NO_ENOUGH_DATA",
            "samples": sample_count,
            "minimum": 60,
            "automatic_promotion": False,
            "manual_approval_required": True,
        }

    def advance_timestamp_boundary(index: int) -> int:
        if index <= 0 or index >= sample_count:
            return index
        previous = clean[index - 1]
        group = previous["fixture_id"] or previous["timestamp"]
        if not group:
            return index
        while index < sample_count and (
            clean[index]["fixture_id"] or clean[index]["timestamp"]
        ) == group:
            index += 1
        return index

    initial_train = advance_timestamp_boundary(max(30, sample_count // 2))
    desired_folds = max(min_folds, 5)
    test_size = max(12, (sample_count - initial_train) // desired_folds)
    folds: list[dict[str, Any]] = []
    evaluation: list[dict[str, Any]] = []
    test_start = initial_train
    while test_start < sample_count:
        test_end = advance_timestamp_boundary(min(sample_count, test_start + test_size))
        training_rows = [
            {
                "timestamp": item["timestamp"],
                "fixture_id": item["fixture_id"],
                "market": item["market"],
                "league": item["league"],
                "current_probability": item["values"][0],
                "dixon_coles_probability": item["values"][1],
                "market_probability": item["values"][2],
                "target": item["target"],
            }
            for item in clean[:test_start]
        ]
        challenger = train_candidate_state(
            training_rows,
            min_segment_samples=int(os.getenv("BETBOT_QUALITY_SEGMENT_MIN_SAMPLES", "500")),
        )
        if challenger.get("status") != "TRAINED_TIME_SAFE":
            break
        fold_records: list[dict[str, Any]] = []
        for item in clean[test_start:test_end]:
            challenger_probability = _state_predict(
                item["values"], challenger, item["market"], item["league"]
            )
            champion_probability = _state_predict(
                item["values"], champion, item["market"], item["league"]
            )
            current_probability = item["values"][0]
            record = {
                **item,
                "challenger_probability": challenger_probability,
                "champion_probability": champion_probability,
                "current_probability": current_probability,
                "challenger_brier": (challenger_probability - item["target"]) ** 2,
                "champion_brier": (champion_probability - item["target"]) ** 2,
                "challenger_log_loss": -(
                    item["target"] * math.log(max(1e-8, challenger_probability))
                    + (1 - item["target"])
                    * math.log(max(1e-8, 1 - challenger_probability))
                ),
                "champion_log_loss": -(
                    item["target"] * math.log(max(1e-8, champion_probability))
                    + (1 - item["target"])
                    * math.log(max(1e-8, 1 - champion_probability))
                ),
            }
            fold_records.append(record)
            evaluation.append(record)
        targets = [item["target"] for item in fold_records]
        odds = [item["odds"] for item in fold_records]
        closing_odds = [item["closing_odds"] for item in fold_records]
        folds.append({
            "fold": len(folds) + 1,
            "train_samples": test_start,
            "test_samples": len(fold_records),
            "test_start_timestamp": fold_records[0]["timestamp"] if fold_records else "",
            "test_end_timestamp": fold_records[-1]["timestamp"] if fold_records else "",
            "challenger": _metrics(
                [item["challenger_probability"] for item in fold_records],
                targets, odds, closing_odds, min_edge
            ),
            "champion": _metrics(
                [item["champion_probability"] for item in fold_records],
                targets, odds, closing_odds, min_edge
            ),
        })
        test_start = test_end

    targets = [item["target"] for item in evaluation]
    odds = [item["odds"] for item in evaluation]
    closing_odds = [item["closing_odds"] for item in evaluation]
    challenger_metrics = _metrics(
        [item["challenger_probability"] for item in evaluation],
        targets, odds, closing_odds, min_edge
    )
    champion_metrics = _metrics(
        [item["champion_probability"] for item in evaluation],
        targets, odds, closing_odds, min_edge
    )
    current_metrics = _metrics(
        [item["current_probability"] for item in evaluation],
        targets, odds, closing_odds, min_edge
    )
    brier_differences = [
        item["champion_brier"] - item["challenger_brier"] for item in evaluation
    ]
    brier_ci = _paired_ci(brier_differences)
    log_loss_ci = _paired_ci([
        item["champion_log_loss"] - item["challenger_log_loss"]
        for item in evaluation
    ])
    brier_gain = champion_metrics["brier_score"] - challenger_metrics["brier_score"]
    log_gain = champion_metrics["log_loss"] - challenger_metrics["log_loss"]
    market_slices = _slice_report(evaluation, "market", max(20, len(evaluation) // 100))
    source_slices = _slice_report(evaluation, "source", max(20, len(evaluation) // 100))
    league_slices = _slice_report(evaluation, "league", max(20, len(evaluation) // 100))
    drift = probability_drift_report(
        [item["values"][0] for item in clean[:initial_train]],
        [item["values"][0] for item in evaluation],
    )
    enough = len(evaluation) >= min(min_test_samples, max(30, sample_count // 4)) and len(folds) >= min_folds
    calibration_ok = (
        challenger_metrics.get("calibration_error", 1.0)
        <= champion_metrics.get("calibration_error", 1.0) + 0.01
    )
    risk_ok = (
        challenger_metrics.get("max_drawdown_units", 0.0)
        <= champion_metrics.get("max_drawdown_units", 0.0) * 1.10 + 2.0
    )
    yield_ok = True
    if min(challenger_metrics.get("bets", 0), champion_metrics.get("bets", 0)) >= 30:
        yield_ok = challenger_metrics["yield"] >= champion_metrics["yield"] - 0.01
    clv_ok = True
    if min(challenger_metrics.get("clv_samples", 0), champion_metrics.get("clv_samples", 0)) >= 30:
        clv_ok = challenger_metrics["mean_clv"] >= champion_metrics["mean_clv"] - 0.005
    slices_ok = (
        market_slices["non_degrading_ratio"] >= 0.60
        and source_slices["non_degrading_ratio"] >= 0.60
        and league_slices["non_degrading_ratio"] >= 0.60
    )
    gates = {
        "enough_future_samples": enough,
        "brier_improvement": brier_gain >= min_brier_improvement,
        "log_loss_improvement": log_gain >= min_log_loss_improvement,
        "brier_confidence_interval_positive": brier_ci["lower"] > 0.0,
        "log_loss_confidence_interval_positive": log_loss_ci["lower"] > 0.0,
        "calibration_not_degraded": calibration_ok,
        "drawdown_within_limit": risk_ok,
        "yield_not_materially_degraded": yield_ok,
        "clv_not_materially_degraded": clv_ok,
        "slice_stability": slices_ok,
        "no_critical_probability_drift": drift.get("status") != "DRIFT_ALERT",
        "beats_raw_current_model": (
            challenger_metrics["brier_score"] <= current_metrics["brier_score"]
            and challenger_metrics["log_loss"] <= current_metrics["log_loss"]
        ),
    }
    passed = all(gates.values())
    return {
        "status": "POSITIVE_VALIDATION_MANUAL_APPROVAL" if passed else "REJECTED_OR_REVIEW",
        "method": "expanding_window_walk_forward",
        "chronological_order": True,
        "folds": len(folds),
        "evaluated_samples": len(evaluation),
        "champion_kind": "active_state" if champion else "raw_current_model",
        "challenger": challenger_metrics,
        "champion": champion_metrics,
        "raw_current_model": current_metrics,
        "brier_improvement": round(brier_gain, 8),
        "log_loss_improvement": round(log_gain, 8),
        "brier_improvement_ci95": brier_ci,
        "log_loss_improvement_ci95": log_loss_ci,
        "required_brier_improvement": min_brier_improvement,
        "required_log_loss_improvement": min_log_loss_improvement,
        "minimum_test_samples": min_test_samples,
        "minimum_folds": min_folds,
        "market_slices": market_slices,
        "source_slices": source_slices,
        "league_slices": league_slices,
        "probability_drift": drift,
        "gates": gates,
        "fold_details": folds,
        "final_candidate_not_scored_on_training_history": True,
        "automatic_promotion": False,
        "manual_approval_required": True,
    }
