"""Dependency-light quality upgrade algorithms for safe shadow evaluation.

Nothing in this module changes a live recommendation. It provides independent
market de-vigging, Dixon-Coles probabilities, learned stacking, beta
calibration and an uncertainty-aware abstention decision.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
from statistics import pstdev
from typing import Any, Iterable, Mapping, Sequence


def _num(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        result = float(str(value).replace("%", "").replace(",", ".").strip())
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _prob(value: Any, default: float | None = None) -> float | None:
    result = _num(value, default)
    if result is None:
        return None
    if result > 1.0:
        result /= 100.0
    return max(1e-6, min(1.0 - 1e-6, result))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-35.0, min(35.0, value))))


def no_vig_probabilities(odds: Mapping[str, Any], method: str = "power") -> dict[str, float]:
    """Remove bookmaker margin using proportional or power normalization."""
    implied = {}
    for key, value in odds.items():
        decimal = _num(value)
        if decimal is not None and decimal > 1.0:
            implied[str(key)] = 1.0 / decimal
    if not implied:
        return {}
    if method == "proportional" or len(implied) == 1:
        total = sum(implied.values())
        return {key: round(value / total, 8) for key, value in implied.items()}
    if method != "power":
        raise ValueError("method must be 'power' or 'proportional'")
    low, high = 0.01, 10.0
    for _ in range(80):
        exponent = (low + high) / 2.0
        if sum(value**exponent for value in implied.values()) > 1.0:
            low = exponent
        else:
            high = exponent
    exponent = (low + high) / 2.0
    adjusted = {key: value**exponent for key, value in implied.items()}
    total = sum(adjusted.values())
    return {key: round(value / total, 8) for key, value in adjusted.items()}


class DixonColesEngine:
    """Low-score-corrected bivariate football score model."""

    def __init__(self, rho: float = -0.08, max_goals: int = 10):
        self.rho = max(-0.25, min(0.25, float(rho)))
        self.max_goals = max(5, int(max_goals))

    @staticmethod
    def _poisson(rate: float, goals: int) -> float:
        return math.exp(-rate) * rate**goals / math.factorial(goals)

    def _tau(self, home: int, away: int, home_xg: float, away_xg: float) -> float:
        if home == 0 and away == 0:
            return 1.0 - home_xg * away_xg * self.rho
        if home == 0 and away == 1:
            return 1.0 + home_xg * self.rho
        if home == 1 and away == 0:
            return 1.0 + away_xg * self.rho
        if home == 1 and away == 1:
            return 1.0 - self.rho
        return 1.0

    def score_matrix(self, home_xg: float, away_xg: float) -> dict[tuple[int, int], float]:
        home_xg = max(0.05, float(home_xg))
        away_xg = max(0.05, float(away_xg))
        matrix = {}
        for home in range(self.max_goals + 1):
            for away in range(self.max_goals + 1):
                probability = self._poisson(home_xg, home) * self._poisson(away_xg, away)
                probability *= max(0.01, self._tau(home, away, home_xg, away_xg))
                matrix[(home, away)] = probability
        total = sum(matrix.values())
        return {score: probability / total for score, probability in matrix.items()}

    def market_probabilities(self, home_xg: float, away_xg: float) -> dict[str, float]:
        matrix = self.score_matrix(home_xg, away_xg)
        result = {key: 0.0 for key in (
            "HOME_WIN", "DRAW", "AWAY_WIN", "HOME_OR_DRAW", "AWAY_OR_DRAW",
            "HOME_OR_AWAY", "BTTS_YES", "BTTS_NO", "OVER_0_5", "UNDER_0_5",
            "OVER_1_5", "UNDER_1_5", "OVER_2_5", "UNDER_2_5",
            "OVER_3_5", "UNDER_3_5", "OVER_4_5", "UNDER_4_5",
        )}
        for (home, away), probability in matrix.items():
            total = home + away
            result["HOME_WIN"] += probability if home > away else 0.0
            result["DRAW"] += probability if home == away else 0.0
            result["AWAY_WIN"] += probability if home < away else 0.0
            result["HOME_OR_DRAW"] += probability if home >= away else 0.0
            result["AWAY_OR_DRAW"] += probability if home <= away else 0.0
            result["HOME_OR_AWAY"] += probability if home != away else 0.0
            result["BTTS_YES"] += probability if home > 0 and away > 0 else 0.0
            result["BTTS_NO"] += probability if home == 0 or away == 0 else 0.0
            for line in (0.5, 1.5, 2.5, 3.5, 4.5):
                suffix = str(line).replace(".", "_")
                result[f"OVER_{suffix}"] += probability if total > line else 0.0
                result[f"UNDER_{suffix}"] += probability if total < line else 0.0
        return {key: round(value, 8) for key, value in result.items()}

    def predict_market(self, market: str, home_xg: float, away_xg: float) -> float | None:
        key = str(market or "").upper().replace(".", "_").replace(" ", "_")
        aliases = {
            "1": "HOME_WIN", "X": "DRAW", "2": "AWAY_WIN",
            "DOUBLE_1X": "HOME_OR_DRAW", "1X": "HOME_OR_DRAW",
            "DOUBLE_X2": "AWAY_OR_DRAW", "X2": "AWAY_OR_DRAW",
            "DOUBLE_12": "HOME_OR_AWAY", "12": "HOME_OR_AWAY",
            "OVER_05": "OVER_0_5", "UNDER_05": "UNDER_0_5",
            "OVER_15": "OVER_1_5", "UNDER_15": "UNDER_1_5",
            "OVER_25": "OVER_2_5", "UNDER_25": "UNDER_2_5",
            "OVER_35": "OVER_3_5", "UNDER_35": "UNDER_3_5",
            "OVER_45": "OVER_4_5", "UNDER_45": "UNDER_4_5",
        }
        return self.market_probabilities(home_xg, away_xg).get(aliases.get(key, key))


def learn_stacking_weights(
    predictions: Sequence[Sequence[float]],
    targets: Sequence[int],
    epochs: int = 350,
    learning_rate: float = 0.03,
) -> list[float]:
    """Learn non-negative simplex weights by minimizing log loss."""
    if not predictions or len(predictions) != len(targets):
        raise ValueError("predictions and targets must be non-empty and aligned")
    width = len(predictions[0])
    if width == 0 or any(len(row) != width for row in predictions):
        raise ValueError("prediction rows must have equal positive width")
    weights = [1.0 / width] * width
    for _ in range(max(1, int(epochs))):
        gradient = [0.0] * width
        for row, target in zip(predictions, targets):
            row = [max(1e-5, min(1.0 - 1e-5, float(value))) for value in row]
            mixture = max(1e-5, min(1.0 - 1e-5, sum(weight * value for weight, value in zip(weights, row))))
            factor = (mixture - int(target)) / (mixture * (1.0 - mixture))
            for index, value in enumerate(row):
                gradient[index] += factor * value / len(predictions)
        updated = [
            weight * math.exp(max(-20.0, min(20.0, -learning_rate * grad)))
            for weight, grad in zip(weights, gradient)
        ]
        total = sum(updated)
        weights = [value / total for value in updated]
    return [round(weight, 8) for weight in weights]


class BetaCalibrator:
    """Three-parameter beta calibration with light regularization."""

    def __init__(self, a: float = 1.0, b: float = 1.0, c: float = 0.0):
        self.a, self.b, self.c = float(a), float(b), float(c)

    def fit(
        self,
        probabilities: Sequence[float],
        targets: Sequence[int],
        epochs: int = 600,
        learning_rate: float = 0.015,
    ) -> "BetaCalibrator":
        if len(probabilities) != len(targets) or len(probabilities) < 8:
            return self
        for _ in range(max(1, int(epochs))):
            gradients = [0.0, 0.0, 0.0]
            for probability, target in zip(probabilities, targets):
                probability = max(1e-5, min(1.0 - 1e-5, float(probability)))
                features = (math.log(probability), -math.log(1.0 - probability), 1.0)
                prediction = _sigmoid(self.a * features[0] + self.b * features[1] + self.c)
                error = prediction - int(target)
                for index, feature in enumerate(features):
                    gradients[index] += error * feature / len(probabilities)
            self.a -= learning_rate * (gradients[0] + 0.0005 * (self.a - 1.0))
            self.b -= learning_rate * (gradients[1] + 0.0005 * (self.b - 1.0))
            self.c -= learning_rate * gradients[2]
        return self

    def predict(self, probability: float) -> float:
        probability = max(1e-5, min(1.0 - 1e-5, float(probability)))
        value = _sigmoid(
            self.a * math.log(probability)
            - self.b * math.log(1.0 - probability)
            + self.c
        )
        return max(0.01, min(0.99, value))

    def to_dict(self) -> dict[str, float]:
        return {"a": self.a, "b": self.b, "c": self.c}


@dataclass(frozen=True)
class QualityAssessment:
    mode: str
    market: str
    current_probability: float
    dixon_coles_probability: float | None
    market_probability_no_vig: float | None
    stacked_probability: float
    calibrated_probability: float
    model_disagreement: float
    uncertainty: float
    conservative_probability: float
    conservative_edge: float | None
    data_quality: float
    decision: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["reasons"] = list(self.reasons)
        return value


def _extract_market_probability(raw: Mapping[str, Any], market: str) -> float | None:
    candidates = raw.get("market_odds") or raw.get("odds_1x2") or raw.get("outcome_odds")
    if isinstance(candidates, Mapping):
        probabilities = no_vig_probabilities(candidates, "power")
        aliases = {
            "HOME_WIN": ("HOME_WIN", "1", "HOME"),
            "DRAW": ("DRAW", "X"),
            "AWAY_WIN": ("AWAY_WIN", "2", "AWAY"),
        }
        for key in aliases.get(market, (market,)):
            if key in probabilities:
                return probabilities[key]
    return None


def _load_state(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path or os.getenv("BETBOT_QUALITY_STATE", "data/quality_shadow_state.json"))
    if not target.exists():
        return {}
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}


def assess_quality(
    raw: Mapping[str, Any],
    current_output: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
) -> QualityAssessment:
    """Evaluate upgraded models without mutating current_output."""
    market = str(
        current_output.get("market") or raw.get("market") or raw.get("typ") or "UNKNOWN"
    ).upper().replace(".", "_").replace(" ", "_")
    current = _prob(current_output.get("probability") or raw.get("probability"), 0.5) or 0.5
    home_xg = _num(raw.get("home_xg", raw.get("xg_home")))
    away_xg = _num(raw.get("away_xg", raw.get("xg_away")))
    dc_probability = None
    if home_xg is not None and away_xg is not None and home_xg >= 0 and away_xg >= 0:
        rho = _num(raw.get("dixon_coles_rho"), -0.08)
        dc_probability = DixonColesEngine(rho=rho if rho is not None else -0.08).predict_market(
            market, home_xg, away_xg
        )
    market_probability = _extract_market_probability(raw, market)
    sources = {"current": current, "dixon_coles": dc_probability, "market": market_probability}
    available = {key: value for key, value in sources.items() if value is not None}
    state = dict(state or _load_state())
    segment_models = state.get("segment_models", {})
    if isinstance(segment_models, Mapping):
        league = str(raw.get("league") or raw.get("liga") or "")
        selected = (
            segment_models.get(f"market::{market}")
            or segment_models.get(f"league::{league}")
        )
        if isinstance(selected, Mapping):
            state = dict(selected)
    configured = state.get("stacking_weights", {})
    configured = configured if isinstance(configured, Mapping) else {}
    default_weights = {"current": 0.45, "dixon_coles": 0.35, "market": 0.20}
    raw_weights = {
        key: max(0.0, _num(configured.get(key), default_weights[key]) or 0.0)
        for key in available
    }
    weight_total = sum(raw_weights.values()) or 1.0
    stacked = sum(available[key] * raw_weights[key] for key in available) / weight_total
    beta = state.get("beta_calibration", {})
    beta = beta if isinstance(beta, Mapping) else {}
    calibrator = BetaCalibrator(
        _num(beta.get("a"), 1.0) or 1.0,
        _num(beta.get("b"), 1.0) or 1.0,
        _num(beta.get("c"), 0.0) or 0.0,
    )
    calibrated = calibrator.predict(stacked)
    disagreement = pstdev(list(available.values())) if len(available) > 1 else 0.0
    supplied_quality = _prob(raw.get("data_quality"))
    if supplied_quality is None:
        completeness = sum(value is not None for value in (home_xg, away_xg, market_probability)) / 3.0
        supplied_quality = 0.45 + 0.45 * completeness
    data_quality = max(0.0, min(1.0, supplied_quality))
    uncertainty = min(0.35, 0.025 + disagreement * 1.35 + (1.0 - data_quality) * 0.18)
    conservative = max(0.01, calibrated - 1.64 * uncertainty)
    bookmaker_odds = _num(
        current_output.get("bookmaker_odds", raw.get("odds", raw.get("kurs_buk")))
    )
    conservative_edge = (
        conservative * bookmaker_odds - 1.0
        if bookmaker_odds is not None and bookmaker_odds > 1.0
        else None
    )
    reasons = []
    if dc_probability is None:
        reasons.append("missing_xg_or_unsupported_market")
    if market_probability is None:
        reasons.append("missing_complete_market_odds")
    if data_quality < 0.60:
        reasons.append("low_data_quality")
    if disagreement > 0.12:
        reasons.append("high_model_disagreement")
    if conservative_edge is None:
        reasons.append("missing_bookmaker_odds")
    elif conservative_edge < 0.02:
        reasons.append("insufficient_conservative_edge")
    if (
        data_quality < 0.50
        or disagreement > 0.18
        or (conservative_edge is not None and conservative_edge < 0.0)
    ):
        decision = "PASS"
    elif reasons:
        decision = "REVIEW"
    else:
        decision = "ACCEPT"
    return QualityAssessment(
        mode="shadow_only_no_runtime_effect",
        market=market,
        current_probability=round(current, 6),
        dixon_coles_probability=round(dc_probability, 6) if dc_probability is not None else None,
        market_probability_no_vig=round(market_probability, 6) if market_probability is not None else None,
        stacked_probability=round(stacked, 6),
        calibrated_probability=round(calibrated, 6),
        model_disagreement=round(disagreement, 6),
        uncertainty=round(uncertainty, 6),
        conservative_probability=round(conservative, 6),
        conservative_edge=round(conservative_edge, 6) if conservative_edge is not None else None,
        data_quality=round(data_quality, 4),
        decision=decision,
        reasons=tuple(reasons),
    )


def _target(row: Mapping[str, Any]) -> int | None:
    value = row.get("target", row.get("won", row.get("result", row.get("outcome"))))
    if value in (1, True, "1", "WON", "WIN", "won", "win"):
        return 1
    if value in (0, False, "0", "LOST", "LOSS", "lost", "loss"):
        return 0
    return None


def train_time_safe_state(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Fit stack/calibration on chronological partitions and score holdout only."""
    clean = []
    for row in rows:
        target = _target(row)
        predictions = [
            _prob(row.get(key))
            for key in ("current_probability", "dixon_coles_probability", "market_probability")
        ]
        if target is not None and all(value is not None for value in predictions):
            clean.append((predictions, target))
    if len(clean) < 30:
        return {"status": "NO_ENOUGH_DATA", "samples": len(clean), "minimum": 30}
    train_end = max(15, int(len(clean) * 0.65))
    calibration_end = max(train_end + 8, int(len(clean) * 0.82))
    training = clean[:train_end]
    calibration = clean[train_end:calibration_end]
    holdout = clean[calibration_end:]
    weights = learn_stacking_weights(
        [row for row, _ in training], [target for _, target in training]
    )

    def mix(values: Sequence[float]) -> float:
        return sum(weight * value for weight, value in zip(weights, values))

    calibrator = BetaCalibrator().fit(
        [mix(row) for row, _ in calibration],
        [target for _, target in calibration],
    )
    predictions = [calibrator.predict(mix(row)) for row, _ in holdout]
    targets = [target for _, target in holdout]
    brier = sum(
        (prediction - target) ** 2 for prediction, target in zip(predictions, targets)
    ) / len(targets)
    log_loss = -sum(
        target * math.log(max(1e-8, prediction))
        + (1 - target) * math.log(max(1e-8, 1 - prediction))
        for prediction, target in zip(predictions, targets)
    ) / len(targets)
    return {
        "status": "TRAINED_TIME_SAFE",
        "samples": len(clean),
        "split": {
            "train": len(training),
            "calibration": len(calibration),
            "holdout": len(holdout),
        },
        "stacking_weights": dict(
            zip(("current", "dixon_coles", "market"), weights)
        ),
        "beta_calibration": calibrator.to_dict(),
        "holdout_metrics": {
            "brier_score": round(brier, 8),
            "log_loss": round(log_loss, 8),
        },
    }


def probability_drift_report(
    reference: Sequence[float],
    current: Sequence[float],
    bins: int = 10,
) -> dict[str, Any]:
    """Population-stability drift check for model probabilities."""
    reference = [value for item in reference if (value := _prob(item)) is not None]
    current = [value for item in current if (value := _prob(item)) is not None]
    if len(reference) < 20 or len(current) < 20:
        return {
            "status": "NO_ENOUGH_DATA",
            "reference_samples": len(reference),
            "current_samples": len(current),
        }
    bins = max(4, min(20, int(bins)))
    epsilon = 1e-6

    def distribution(values: Sequence[float]) -> list[float]:
        counts = [0] * bins
        for value in values:
            counts[min(bins - 1, int(value * bins))] += 1
        return [max(epsilon, count / len(values)) for count in counts]

    expected = distribution(reference)
    observed = distribution(current)
    psi = sum(
        (actual - base) * math.log(actual / base)
        for base, actual in zip(expected, observed)
    )
    mean_reference = sum(reference) / len(reference)
    mean_current = sum(current) / len(current)
    mean_shift = mean_current - mean_reference
    if psi >= 0.25 or abs(mean_shift) >= 0.10:
        status = "DRIFT_ALERT"
    elif psi >= 0.10 or abs(mean_shift) >= 0.05:
        status = "DRIFT_WARNING"
    else:
        status = "STABLE"
    return {
        "status": status,
        "psi": round(psi, 8),
        "mean_reference": round(mean_reference, 6),
        "mean_current": round(mean_current, 6),
        "mean_shift": round(mean_shift, 6),
        "reference_samples": len(reference),
        "current_samples": len(current),
    }


def portfolio_fractional_kelly(
    candidates: Iterable[Mapping[str, Any]],
    bankroll: float,
    fraction: float = 0.25,
    single_cap: float = 0.02,
    total_cap: float = 0.06,
    group_cap: float = 0.03,
) -> list[dict[str, Any]]:
    """Allocate conservative stakes with total and correlated-group caps."""
    bankroll = max(0.0, float(bankroll))
    fraction = max(0.0, min(1.0, float(fraction)))
    single_cap = max(0.0, float(single_cap))
    total_cap = max(single_cap, float(total_cap))
    group_cap = max(single_cap, float(group_cap))
    prepared = []
    for index, candidate in enumerate(candidates):
        probability = _prob(candidate.get("probability"))
        odds = _num(candidate.get("odds"))
        if probability is None or odds is None or odds <= 1.0:
            continue
        edge = probability * odds - 1.0
        full_kelly = max(0.0, ((odds - 1.0) * probability - (1.0 - probability)) / (odds - 1.0))
        requested = min(single_cap, full_kelly * fraction)
        prepared.append((edge, index, dict(candidate), requested))
    prepared.sort(key=lambda item: item[0], reverse=True)
    total_used = 0.0
    group_used: dict[str, float] = {}
    allocations = []
    for edge, index, candidate, requested in prepared:
        group = str(
            candidate.get("correlation_group")
            or candidate.get("match_id")
            or candidate.get("match")
            or f"independent_{index}"
        )
        available_total = max(0.0, total_cap - total_used)
        available_group = max(0.0, group_cap - group_used.get(group, 0.0))
        allocated = min(requested, available_total, available_group)
        total_used += allocated
        group_used[group] = group_used.get(group, 0.0) + allocated
        allocations.append({
            **candidate,
            "edge": round(edge, 6),
            "stake_fraction": round(allocated, 6),
            "stake": round(bankroll * allocated, 2),
            "portfolio_status": "ALLOCATED" if allocated > 0 else "CAP_REACHED",
        })
    return allocations
