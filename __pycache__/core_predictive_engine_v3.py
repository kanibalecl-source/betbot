"""Independent predictive core.
This module deliberately does NOT use bookmaker odds to create probabilities.
Odds are only allowed later in MarketComparisonEngineV3.
"""
from __future__ import annotations

import math
from typing import Dict, Tuple, Optional

from probability_utils import clamp_probability


def _poisson(lmbda: float, k: int) -> float:
    if lmbda < 0:
        return 0.0
    return math.exp(-lmbda) * (lmbda ** k) / math.factorial(k)


class CorePredictiveEngineV3:
    def __init__(self, max_goals: int = 10):
        self.max_goals = int(max_goals)

    def score_matrix(self, home_xg: float, away_xg: float) -> Dict[Tuple[int, int], float]:
        home_xg = max(float(home_xg), 0.05)
        away_xg = max(float(away_xg), 0.05)
        matrix = {}
        total = 0.0
        for h in range(self.max_goals + 1):
            for a in range(self.max_goals + 1):
                p = _poisson(home_xg, h) * _poisson(away_xg, a)
                matrix[(h, a)] = p
                total += p
        if total > 0:
            matrix = {k: v / total for k, v in matrix.items()}
        return matrix

    def market_probabilities(self, home_xg: float, away_xg: float) -> Dict[str, float]:
        m = self.score_matrix(home_xg, away_xg)
        out = {
            'HOME_WIN': 0.0,
            'DRAW': 0.0,
            'AWAY_WIN': 0.0,
            'HOME_OR_DRAW': 0.0,
            'AWAY_OR_DRAW': 0.0,
            'HOME_OR_AWAY': 0.0,
            'BTTS_YES': 0.0,
            'BTTS_NO': 0.0,
            'OVER_1_5': 0.0,
            'UNDER_1_5': 0.0,
            'OVER_2_5': 0.0,
            'UNDER_2_5': 0.0,
            'OVER_3_5': 0.0,
            'UNDER_3_5': 0.0,
        }
        for (h, a), p in m.items():
            total = h + a
            if h > a: out['HOME_WIN'] += p
            if h == a: out['DRAW'] += p
            if a > h: out['AWAY_WIN'] += p
            if h >= a: out['HOME_OR_DRAW'] += p
            if a >= h: out['AWAY_OR_DRAW'] += p
            if h != a: out['HOME_OR_AWAY'] += p
            if h > 0 and a > 0: out['BTTS_YES'] += p
            if h == 0 or a == 0: out['BTTS_NO'] += p
            for line in (1.5, 2.5, 3.5):
                key = str(line).replace('.', '_')
                if total > line: out[f'OVER_{key}'] += p
                if total < line: out[f'UNDER_{key}'] += p
        return {k: round(clamp_probability(v, 0.001, 0.999), 6) for k, v in out.items()}

    def predict_market(self, market: str, home_xg: float, away_xg: float) -> Optional[float]:
        if not market:
            return None
        market = str(market).upper().replace('.', '_')
        return self.market_probabilities(home_xg, away_xg).get(market)

    def most_likely_scores(self, home_xg: float, away_xg: float, top_n: int = 5):
        matrix = self.score_matrix(home_xg, away_xg)
        rows = sorted(matrix.items(), key=lambda x: x[1], reverse=True)[:top_n]
        return [{'score': f'{h}:{a}', 'probability': round(p, 6)} for (h, a), p in rows]
