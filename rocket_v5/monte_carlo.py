from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any
import math
import random

from .utils import clamp


@dataclass
class SimulationResultV5:
    runs: int
    markets: Dict[str, float]
    score_probs: Dict[str, float]
    fair_odds: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MonteCarloEngineV5:
    def __init__(self, runs: int = 75000, max_goals: int = 10, seed: int = 42):
        self.runs = int(runs)
        self.max_goals = int(max_goals)
        self.random = random.Random(seed)

    def poisson_sample(self, lam: float) -> int:
        lam = clamp(lam, 0.01, 6.5)
        L = math.exp(-lam)
        k = 0
        p = 1.0
        while p > L and k < self.max_goals:
            k += 1
            p *= self.random.random()
        return max(0, k - 1)

    def simulate(self, home_xg: float, away_xg: float, runs: int | None = None) -> SimulationResultV5:
        n = int(runs or self.runs)
        counts = {
            "HOME_WIN": 0, "DRAW": 0, "AWAY_WIN": 0, "OVER_1_5": 0, "OVER_2_5": 0,
            "OVER_3_5": 0, "BTTS_YES": 0, "HOME_DNB": 0, "AWAY_DNB": 0,
            "DOUBLE_1X": 0, "DOUBLE_X2": 0, "DOUBLE_12": 0,
        }
        score_counts: Dict[str, int] = {}
        for _ in range(n):
            h = self.poisson_sample(home_xg)
            a = self.poisson_sample(away_xg)
            score_counts[f"{h}-{a}"] = score_counts.get(f"{h}-{a}", 0) + 1
            total = h + a
            if h > a: counts["HOME_WIN"] += 1
            if h == a: counts["DRAW"] += 1
            if a > h: counts["AWAY_WIN"] += 1
            if total > 1.5: counts["OVER_1_5"] += 1
            if total > 2.5: counts["OVER_2_5"] += 1
            if total > 3.5: counts["OVER_3_5"] += 1
            if h > 0 and a > 0: counts["BTTS_YES"] += 1
            if h >= a: counts["HOME_DNB"] += 1
            if a >= h: counts["AWAY_DNB"] += 1
            if h >= a: counts["DOUBLE_1X"] += 1
            if a >= h: counts["DOUBLE_X2"] += 1
            if h != a: counts["DOUBLE_12"] += 1
        markets = {k: round(v / n, 6) for k, v in counts.items()}
        score_probs = dict(sorted(((k, round(v/n, 6)) for k, v in score_counts.items()), key=lambda kv: kv[1], reverse=True)[:20])
        fair_odds = {k: round(1/v, 4) for k, v in markets.items() if v > 0}
        return SimulationResultV5(n, markets, score_probs, fair_odds)
