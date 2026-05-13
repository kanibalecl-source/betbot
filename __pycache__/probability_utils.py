"""Probability and value helpers for bookmaker-independent modelling.
All model probabilities are decimals in range 0.00-1.00.
Bookmaker odds are used only for market comparison, EV and CLV.
"""
from __future__ import annotations

from typing import Dict, Optional


def normalize_probability(value, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace('%', '').replace(',', '.').strip()
            if value.lower() in {'', 'none', 'null', 'nan'}:
                return default
        p = float(value)
        if p > 1.0:
            p /= 100.0
        if p < 0 or p > 1:
            return default
        return p
    except Exception:
        return default


def clamp_probability(p: float, low: float = 0.01, high: float = 0.99) -> float:
    return max(low, min(high, float(p)))


def fair_odds(probability: float) -> Optional[float]:
    p = normalize_probability(probability)
    if not p or p <= 0:
        return None
    return round(1.0 / p, 4)


def implied_probability(odds: float) -> Optional[float]:
    try:
        odds = float(odds)
        if odds <= 1:
            return None
        return 1.0 / odds
    except Exception:
        return None


def no_vig_probabilities(outcome_odds: Dict[str, float]) -> Dict[str, float]:
    implied = {k: implied_probability(v) for k, v in outcome_odds.items()}
    implied = {k: v for k, v in implied.items() if v is not None and v > 0}
    total = sum(implied.values())
    if total <= 0:
        return {}
    return {k: round(v / total, 6) for k, v in implied.items()}


def expected_value_decimal(probability: float, odds: float) -> Optional[float]:
    p = normalize_probability(probability)
    try:
        odds = float(odds)
    except Exception:
        return None
    if p is None or odds <= 1:
        return None
    return round((p * odds) - 1.0, 6)


def edge_decimal(model_probability: float, market_probability: float) -> Optional[float]:
    p = normalize_probability(model_probability)
    m = normalize_probability(market_probability)
    if p is None or m is None:
        return None
    return round(p - m, 6)
