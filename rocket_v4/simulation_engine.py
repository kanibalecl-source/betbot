from __future__ import annotations

from typing import Dict, Tuple, List
from .probability import poisson_pmf, clamp_probability


class SimulationEngineV4:
    """Goal distribution and market probabilities from independent xG."""

    def __init__(self, max_goals: int = 10):
        self.max_goals = max_goals

    def score_matrix(self, home_xg: float, away_xg: float) -> Dict[Tuple[int, int], float]:
        hx, ax = max(home_xg, 0.01), max(away_xg, 0.01)
        matrix = {}
        total = 0.0
        for h in range(self.max_goals + 1):
            hp = poisson_pmf(hx, h)
            for a in range(self.max_goals + 1):
                p = hp * poisson_pmf(ax, a)
                # Dixon-Coles light correction for low scoring correlation.
                if h == 0 and a == 0: p *= 1.06
                elif h == 1 and a == 1: p *= 1.03
                elif h == 1 and a == 0: p *= 0.985
                elif h == 0 and a == 1: p *= 0.985
                matrix[(h, a)] = p
                total += p
        return {k: v / total for k, v in matrix.items()} if total else matrix

    def markets(self, home_xg: float, away_xg: float) -> Dict[str, float]:
        m = self.score_matrix(home_xg, away_xg)
        out = {k: 0.0 for k in [
            "HOME_WIN", "DRAW", "AWAY_WIN", "HOME_OR_DRAW", "AWAY_OR_DRAW", "HOME_OR_AWAY",
            "BTTS_YES", "BTTS_NO", "OVER_0_5", "OVER_1_5", "OVER_2_5", "OVER_3_5", "OVER_4_5",
            "UNDER_0_5", "UNDER_1_5", "UNDER_2_5", "UNDER_3_5", "UNDER_4_5",
        ]}
        for (h, a), p in m.items():
            total = h + a
            if h > a: out["HOME_WIN"] += p
            if h == a: out["DRAW"] += p
            if a > h: out["AWAY_WIN"] += p
            if h >= a: out["HOME_OR_DRAW"] += p
            if a >= h: out["AWAY_OR_DRAW"] += p
            if h != a: out["HOME_OR_AWAY"] += p
            if h > 0 and a > 0: out["BTTS_YES"] += p
            else: out["BTTS_NO"] += p
            for line in [0.5,1.5,2.5,3.5,4.5]:
                key = str(line).replace('.', '_')
                if total > line: out[f"OVER_{key}"] += p
                if total < line: out[f"UNDER_{key}"] += p
        return {k: round(clamp_probability(v), 6) for k, v in out.items()}

    def top_scores(self, home_xg: float, away_xg: float, n: int = 7) -> List[dict]:
        rows = sorted(self.score_matrix(home_xg, away_xg).items(), key=lambda kv: kv[1], reverse=True)[:n]
        return [{"score": f"{h}:{a}", "probability": round(p, 6)} for (h,a), p in rows]
