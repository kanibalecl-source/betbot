from __future__ import annotations

from typing import Dict, Optional
from .probability import expected_value, fair_odds, implied_probability, normalize_probability


class MarketComparatorV4:
    """Compares independent model probability with bookmaker odds.

    Bookmaker information is deliberately isolated here.
    """

    def compare(self, model_probability: float, bookmaker_odds: float, market_margin_probability: Optional[float] = None) -> Dict[str, float | str | None]:
        p = normalize_probability(model_probability)
        imp = implied_probability(bookmaker_odds)
        ev = expected_value(p, bookmaker_odds) if p is not None else None
        fair = fair_odds(p) if p is not None else None
        edge = None
        if p is not None:
            edge = p - (market_margin_probability if market_margin_probability is not None else imp)
        return {
            "bookmaker_odds": bookmaker_odds,
            "model_probability": p,
            "fair_odds": round(fair, 4) if fair else None,
            "market_implied_probability": round(imp, 6) if imp else None,
            "edge_decimal": round(edge, 6) if edge is not None else None,
            "ev_decimal": round(ev, 6) if ev is not None else None,
            "value_flag": bool(ev is not None and edge is not None and ev > 0 and edge > 0),
        }
