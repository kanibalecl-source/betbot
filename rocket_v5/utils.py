from __future__ import annotations

import math
from typing import Any


def num(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", [], {}):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1 / (1 + z)
    z = math.exp(x)
    return z / (1 + z)


def implied_probability(decimal_odds: float) -> float:
    odds = num(decimal_odds, 0.0)
    return 1.0 / odds if odds > 1.0 else 0.0


def ev_decimal(probability: float, odds: float) -> float:
    return clamp(probability, 0, 1) * num(odds, 0) - 1.0
