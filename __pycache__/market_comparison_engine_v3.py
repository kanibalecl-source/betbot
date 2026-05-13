"""Bookmaker comparison layer.
This is the only place where odds influence betting decision metrics.
They never create model_probability.
"""
from __future__ import annotations

from typing import Dict, Optional
from probability_utils import implied_probability, no_vig_probabilities, expected_value_decimal, edge_decimal, fair_odds


class MarketComparisonEngineV3:
    def compare_single(self, model_probability: float, odds: float, market_probability: Optional[float] = None) -> Dict:
        raw_market_prob = market_probability if market_probability is not None else implied_probability(odds)
        ev = expected_value_decimal(model_probability, odds)
        edge = edge_decimal(model_probability, raw_market_prob) if raw_market_prob is not None else None
        return {
            'model_probability': round(float(model_probability), 6),
            'bookmaker_odds': float(odds) if odds else None,
            'market_probability_raw': round(raw_market_prob, 6) if raw_market_prob is not None else None,
            'edge_decimal': edge,
            'edge_percent': round(edge * 100, 2) if edge is not None else None,
            'ev_decimal': ev,
            'ev_percent': round(ev * 100, 2) if ev is not None else None,
            'fair_odds_model': fair_odds(model_probability),
            'value_status': self.value_status(ev, edge),
        }

    def compare_1x2_no_vig(self, model_probs: Dict[str, float], odds_1x2: Dict[str, float]) -> Dict[str, Dict]:
        market = no_vig_probabilities(odds_1x2)
        out = {}
        for key, p in model_probs.items():
            if key not in odds_1x2:
                continue
            out[key] = self.compare_single(p, odds_1x2[key], market.get(key))
        return out

    def value_status(self, ev, edge) -> str:
        if ev is None or edge is None:
            return 'NO_MARKET_DATA'
        if ev >= 0.08 and edge >= 0.05:
            return 'STRONG_VALUE'
        if ev >= 0.04 and edge >= 0.03:
            return 'VALUE'
        if ev >= 0.00:
            return 'THIN_VALUE'
        return 'NO_VALUE'
