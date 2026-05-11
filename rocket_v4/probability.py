from __future__ import annotations

import math
from typing import Dict, Iterable, Optional


def clamp_probability(value: Optional[float], low: float = 0.001, high: float = 0.999) -> Optional[float]:
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return min(max(x, low), high)


def normalize_probability(value: Optional[float]) -> Optional[float]:
    """Return probability in 0..1. Values above 1 are treated as percentages."""
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if x > 1.0 and x <= 100.0:
        x /= 100.0
    return clamp_probability(x)


def implied_probability(decimal_odds: float) -> Optional[float]:
    try:
        odds = float(decimal_odds)
    except (TypeError, ValueError):
        return None
    if odds <= 1.0:
        return None
    return clamp_probability(1.0 / odds)


def devig_two_way(odds_a: float, odds_b: float) -> Dict[str, Optional[float]]:
    pa = implied_probability(odds_a)
    pb = implied_probability(odds_b)
    if pa is None or pb is None or pa + pb <= 0:
        return {"a": None, "b": None, "overround": None}
    s = pa + pb
    return {"a": pa / s, "b": pb / s, "overround": s}


def expected_value(probability: float, decimal_odds: float) -> Optional[float]:
    p = normalize_probability(probability)
    try:
        odds = float(decimal_odds)
    except (TypeError, ValueError):
        return None
    if p is None or odds <= 1.0:
        return None
    return p * odds - 1.0


def fair_odds(probability: float) -> Optional[float]:
    p = normalize_probability(probability)
    if p is None or p <= 0:
        return None
    return 1.0 / p


def poisson_pmf(lam: float, k: int) -> float:
    lam = max(float(lam), 0.0001)
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def softmax(scores: Iterable[float]) -> list[float]:
    xs = [float(x) for x in scores]
    if not xs:
        return []
    m = max(xs)
    es = [math.exp(x - m) for x in xs]
    s = sum(es)
    return [e / s for e in es]
