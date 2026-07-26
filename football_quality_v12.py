"""Independent football probability challenger for BetBot v12.

Bookmaker odds are never model inputs.  They are accepted only after the
probability has been frozen, for no-vig benchmarking and value measurement.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import pstdev
from typing import Any, Mapping

from quality_upgrade_engine import BetaCalibrator, DixonColesEngine, no_vig_probabilities


def _number(value: Any) -> float | None:
    try:
        result = float(str(value).replace(",", ".").replace("%", "").strip())
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _probability(value: Any) -> float | None:
    result = _number(value)
    if result is None:
        return None
    if result > 1.0:
        result /= 100.0
    return min(0.99, max(0.01, result))


@dataclass(frozen=True)
class IndependentFootballPrediction:
    sport: str
    market: str
    probability: float
    fair_odds: float
    model_components: dict[str, float]
    model_disagreement: float
    feature_completeness: float
    missing_features: tuple[str, ...]
    bookmaker_used_as_model_input: bool
    market_probability: float | None
    market_edge: float | None
    status: str

    def payload(self) -> dict[str, Any]:
        value = asdict(self)
        value["missing_features"] = list(self.missing_features)
        return value


def build_independent_prediction(
    match: Mapping[str, Any],
    *,
    market: str,
    base_probability: Any,
    bookmaker_odds: Mapping[str, Any] | None = None,
    calibration: Mapping[str, Any] | None = None,
) -> IndependentFootballPrediction:
    normalized_market = str(market).upper().replace(".", "_").replace(" ", "_")
    current = _probability(base_probability)
    home_xg = _number(match.get("home_xg") or match.get("xg_home"))
    away_xg = _number(match.get("away_xg") or match.get("xg_away"))
    home_form = _probability(match.get("home_form_probability"))
    away_form = _probability(match.get("away_form_probability"))
    missing = []
    components: dict[str, float] = {}
    if current is not None:
        components["current_model"] = current
    else:
        missing.append("base_probability")
    if home_xg is not None and away_xg is not None:
        dixon = DixonColesEngine(
            rho=_number(match.get("dixon_coles_rho")) or -0.08
        ).predict_market(normalized_market, home_xg, away_xg)
        if dixon is not None:
            components["dixon_coles"] = dixon
    else:
        missing.extend(
            name
            for name, value in (("home_xg", home_xg), ("away_xg", away_xg))
            if value is None
        )
    if home_form is not None and away_form is not None:
        total = home_form + away_form
        if total > 0:
            components["form"] = home_form / total
    else:
        if home_form is None:
            missing.append("home_form_probability")
        if away_form is None:
            missing.append("away_form_probability")
    if not components:
        probability = 0.5
        status = "ABSTAIN_MISSING_MODEL_DATA"
    else:
        weights = {
            "current_model": 0.50,
            "dixon_coles": 0.35,
            "form": 0.15,
        }
        total_weight = sum(weights[name] for name in components)
        probability = sum(
            components[name] * weights[name] for name in components
        ) / total_weight
        beta = dict(calibration or {})
        probability = BetaCalibrator(
            _number(beta.get("a")) or 1.0,
            _number(beta.get("b")) or 1.0,
            _number(beta.get("c")) or 0.0,
        ).predict(probability)
        status = "SHADOW_CANDIDATE"
    market_probability = None
    market_edge = None
    if bookmaker_odds:
        no_vig = no_vig_probabilities(bookmaker_odds, "power")
        aliases = {
            "HOME_WIN": ("HOME_WIN", "HOME", "1"),
            "DRAW": ("DRAW", "X"),
            "AWAY_WIN": ("AWAY_WIN", "AWAY", "2"),
        }
        market_probability = next(
            (no_vig[key] for key in aliases.get(normalized_market, (normalized_market,)) if key in no_vig),
            None,
        )
        if market_probability is not None:
            market_edge = probability - market_probability
    completeness = len(components) / 3.0
    disagreement = pstdev(components.values()) if len(components) > 1 else 0.0
    if completeness < 0.50 or disagreement > 0.18:
        status = "ABSTAIN_LOW_QUALITY"
    probability = min(0.99, max(0.01, probability))
    return IndependentFootballPrediction(
        sport="football",
        market=normalized_market,
        probability=round(probability, 8),
        fair_odds=round(1.0 / probability, 6),
        model_components={key: round(value, 8) for key, value in components.items()},
        model_disagreement=round(disagreement, 8),
        feature_completeness=round(completeness, 8),
        missing_features=tuple(sorted(set(missing))),
        bookmaker_used_as_model_input=False,
        market_probability=(
            round(market_probability, 8) if market_probability is not None else None
        ),
        market_edge=round(market_edge, 8) if market_edge is not None else None,
        status=status,
    )
