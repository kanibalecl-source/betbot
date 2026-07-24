"""Deterministic drift checks for admitted chronological training data."""
from __future__ import annotations

import math
import os
from collections import Counter
from typing import Any, Mapping, Sequence


def _number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _psi(before: Sequence[float], after: Sequence[float], edges: Sequence[float]) -> float:
    if not before or not after:
        return 0.0
    def distribution(values: Sequence[float]) -> list[float]:
        counts = [0] * (len(edges) + 1)
        for value in values:
            index = next(
                (position for position, edge in enumerate(edges) if value < edge),
                len(edges),
            )
            counts[index] += 1
        return [max(1e-6, count / len(values)) for count in counts]
    left, right = distribution(before), distribution(after)
    return sum((new - old) * math.log(new / old) for old, new in zip(left, right))


def _categorical_tvd(
    before: Sequence[Mapping[str, Any]],
    after: Sequence[Mapping[str, Any]],
    field: str,
) -> float:
    left = Counter(str(row.get(field) or "UNKNOWN") for row in before)
    right = Counter(str(row.get(field) or "UNKNOWN") for row in after)
    keys = set(left) | set(right)
    return 0.5 * sum(
        abs(left[key] / max(1, len(before)) - right[key] / max(1, len(after)))
        for key in keys
    )


def distribution_drift_report(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    minimum = max(100, int(os.getenv("BETBOT_QUALITY_DRIFT_MIN_SAMPLES", "300")))
    if len(rows) < minimum:
        return {
            "status": "WAITING_FOR_SAMPLES",
            "samples": len(rows),
            "minimum_samples": minimum,
        }
    boundary = len(rows) // 2
    before, after = rows[:boundary], rows[boundary:]
    numeric_specs = {
        "current_probability": (0.2, 0.35, 0.5, 0.65, 0.8),
        "dixon_coles_probability": (0.2, 0.35, 0.5, 0.65, 0.8),
        "market_probability": (0.2, 0.35, 0.5, 0.65, 0.8),
        "odds": (1.4, 1.8, 2.2, 3.0, 5.0),
        "home_xg": (0.5, 1.0, 1.5, 2.0, 3.0),
        "away_xg": (0.5, 1.0, 1.5, 2.0, 3.0),
    }
    numeric = {}
    for field, edges in numeric_specs.items():
        old = [value for row in before if (value := _number(row.get(field))) is not None]
        new = [value for row in after if (value := _number(row.get(field))) is not None]
        numeric[field] = round(_psi(old, new, edges), 6)
    categorical = {
        field: round(_categorical_tvd(before, after, field), 6)
        for field in ("source", "market", "league")
    }
    psi_limit = float(os.getenv("BETBOT_QUALITY_MAX_PSI", "0.25"))
    tvd_limit = float(os.getenv("BETBOT_QUALITY_MAX_CATEGORICAL_TVD", "0.30"))
    alerts = [
        f"psi::{field}" for field, value in numeric.items() if value > psi_limit
    ] + [
        f"tvd::{field}" for field, value in categorical.items() if value > tvd_limit
    ]
    return {
        "status": "DRIFT_ALERT" if alerts else "STABLE",
        "samples": len(rows),
        "baseline_samples": len(before),
        "recent_samples": len(after),
        "numeric_psi": numeric,
        "categorical_tvd": categorical,
        "psi_limit": psi_limit,
        "categorical_tvd_limit": tvd_limit,
        "alerts": alerts,
    }
