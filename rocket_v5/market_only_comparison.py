from __future__ import annotations

from typing import Any, Dict

from .utils import clamp, ev_decimal, implied_probability, num


class MarketOnlyComparatorV5:
    """Bookmaker layer. It receives final independent probability and compares it with odds."""

    def compare(self, probability: float, odds: float, min_ev: float = 0.045, min_edge: float = 0.035) -> Dict[str, Any]:
        p = clamp(num(probability, 0.0), 0.0, 1.0)
        o = num(odds, 0.0)
        market_p = implied_probability(o)
        edge = p - market_p
        ev = ev_decimal(p, o)
        status = "ACCEPTED_VALUE" if o > 1 and ev >= min_ev and edge >= min_edge else "REJECTED_NO_VALUE"
        return {
            "status": status,
            "model_probability": round(p, 6),
            "bookmaker_odds": o,
            "market_probability_raw": round(market_p, 6),
            "edge": round(edge, 6),
            "ev": round(ev, 6),
            "fair_odds": round(1/p, 4) if p > 0 else None,
        }
