"""Observational xG diagnostics with market-consistent probabilities."""

from __future__ import annotations

import math
import re
from typing import Optional


PROBABILITY_METHOD = "independent_poisson"
PROBABILITY_VERSION = "stage_b_poisson_v2"
_TOTAL_MARKET = re.compile(r"^(OVER|UNDER)_(\d+)_(\d+)$")


def _finite_non_negative(value: object) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("xG must be a finite non-negative number")
    return number


def _poisson_cdf(max_goals: int, expected_goals: float) -> float:
    """Return P(X <= max_goals) without requiring scipy."""
    if max_goals < 0:
        return 0.0
    term = math.exp(-expected_goals)
    total = term
    for goals in range(1, max_goals + 1):
        term *= expected_goals / goals
        total += term
    return max(0.0, min(1.0, total))


def total_market_probability(
    expected_goals: float,
    direction: str,
    line: float,
) -> float:
    """Probability for full-goal Asian-style lines such as Over/Under 2.5."""
    if line < 0 or abs((line * 2) - round(line * 2)) > 1e-9:
        raise ValueError("unsupported total line")
    # Current target markets use .5 lines, so there is no push state.
    if abs((line % 1) - 0.5) > 1e-9:
        raise ValueError("only half-goal total lines are supported")
    under = _poisson_cdf(math.floor(line), expected_goals)
    return under if direction == "UNDER" else 1.0 - under


def market_probability(
    market: object,
    home_xg: float,
    away_xg: float,
) -> Optional[float]:
    """Return a probability aligned to the selected market, or None."""
    key = str(market or "").strip().upper().replace(".", "_").replace("-", "_")
    total_xg = home_xg + away_xg
    total_match = _TOTAL_MARKET.match(key)
    if total_match:
        direction, whole, decimal = total_match.groups()
        line = float(f"{whole}.{decimal}")
        try:
            return total_market_probability(total_xg, direction, line)
        except ValueError:
            return None

    home_zero = math.exp(-home_xg)
    away_zero = math.exp(-away_xg)
    btts_yes = (1.0 - home_zero) * (1.0 - away_zero)
    if key == "BTTS_YES":
        return btts_yes
    if key == "BTTS_NO":
        return 1.0 - btts_yes

    # Independent Poisson score matrix. The tiny omitted tail is normalized.
    home_win = draw = away_win = mass = 0.0
    home_term = math.exp(-home_xg)
    for home_goals in range(13):
        if home_goals:
            home_term *= home_xg / home_goals
        away_term = math.exp(-away_xg)
        for away_goals in range(13):
            if away_goals:
                away_term *= away_xg / away_goals
            cell = home_term * away_term
            mass += cell
            if home_goals > away_goals:
                home_win += cell
            elif home_goals == away_goals:
                draw += cell
            else:
                away_win += cell
    if mass <= 0:
        return None
    home_win, draw, away_win = home_win / mass, draw / mass, away_win / mass
    probabilities = {
        "HOME_WIN": home_win,
        "DRAW": draw,
        "AWAY_WIN": away_win,
        "DOUBLE_1X": home_win + draw,
        "DOUBLE_X2": draw + away_win,
        "DOUBLE_12": home_win + away_win,
    }
    return probabilities.get(key)


class StageBModelLayer:

    def enrich_pick(
        self,
        pick,
        probability,
        home_xg,
        away_xg,
        minute=0,
        shots_on_target=0,
        dangerous_attacks=0,
        possession=50,
        pressure=50,
        corners=0,
        sharp_score=0,
        clv_score=0,
        market=None,
    ):
        try:
            home = _finite_non_negative(home_xg)
            away = _finite_non_negative(away_xg)
            total_xg = home + away

            over25 = total_market_probability(total_xg, "OVER", 2.5)
            under25 = 1.0 - over25
            selected_probability = market_probability(market, home, away)

            momentum_score = (
                shots_on_target * 4
                + dangerous_attacks * 0.8
                + pressure * 0.5
                + corners * 2
                + sharp_score * 0.6
                + clv_score * 0.4
            )

            if momentum_score >= 90:
                momentum_label = "EXTREME"
            elif momentum_score >= 70:
                momentum_label = "HIGH"
            elif momentum_score >= 45:
                momentum_label = "MEDIUM"
            else:
                momentum_label = "LOW"

            calibrated_conf = probability
            if probability <= 1:
                calibrated_conf = probability * 100
            calibrated_conf += sharp_score * 0.08
            calibrated_conf += (total_xg - 2.4) * 4
            calibrated_conf += clv_score * 0.05
            calibrated_conf = max(1, min(99, calibrated_conf))

            result = dict(pick)
            result.update({
                "advanced_total_xg": round(total_xg, 2),
                # Legacy display fields remain percentages.
                "advanced_over25_prob": round(over25 * 100, 2),
                "advanced_under25_prob": round(under25 * 100, 2),
                # Canonical market-aligned value is a decimal probability.
                "advanced_market_prob": (
                    round(selected_probability, 6)
                    if selected_probability is not None
                    else None
                ),
                "advanced_probability_method": PROBABILITY_METHOD,
                "advanced_probability_version": PROBABILITY_VERSION,
                "advanced_probability_integrity": (
                    "PASS"
                    if abs((over25 + under25) - 1.0) <= 1e-12
                    else "FAIL"
                ),
                "momentum_score": round(momentum_score, 2),
                "momentum_label": momentum_label,
                "confidence_calibrated_v2": round(calibrated_conf, 2),
            })
            return result

        except Exception as exc:
            print(f"STAGE B ERROR: {exc}")
            return {
                "advanced_total_xg": None,
                "advanced_over25_prob": None,
                "advanced_under25_prob": None,
                "advanced_market_prob": None,
                "advanced_probability_method": PROBABILITY_METHOD,
                "advanced_probability_version": PROBABILITY_VERSION,
                "advanced_probability_integrity": "ERROR",
                "momentum_score": 0,
                "momentum_label": "ERROR",
                "confidence_calibrated_v2": 0,
            }
