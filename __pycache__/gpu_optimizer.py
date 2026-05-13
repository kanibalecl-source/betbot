from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

import numpy as np


@dataclass
class MonteCarloResult:
    runs: int
    backend: str
    home_win: float
    draw: float
    away_win: float
    over_05: float
    over_15: float
    over_25: float
    over_35: float
    over_45: float
    btts_yes: float
    expected_home_goals: float
    expected_away_goals: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GPUOptimizer:
    """Vectorized Monte Carlo accelerator.

    Uses CuPy automatically if available, otherwise NumPy. This makes the
    simulation fast in Railway/CPU environments and GPU-ready on machines with
    CUDA installed. No hard dependency on GPU libraries.
    """

    def __init__(self, prefer_gpu: bool = True, seed: Optional[int] = 42):
        self.seed = seed
        self.backend = "numpy"
        self.xp = np
        if prefer_gpu:
            try:
                import cupy as cp  # type: ignore
                self.xp = cp
                self.backend = "cupy_cuda"
            except Exception:
                self.xp = np
                self.backend = "numpy"

    def optimize(self) -> Dict[str, Any]:
        return {"backend": self.backend, "vectorized": True, "gpu_available": self.backend.startswith("cupy")}

    def vectorized_monte_carlo(self, home_xg: float, away_xg: float, runs: int = 100000) -> Dict[str, Any]:
        xp = self.xp
        if self.backend == "numpy":
            rng = np.random.default_rng(self.seed)
            home = rng.poisson(max(0.05, float(home_xg)), int(runs))
            away = rng.poisson(max(0.05, float(away_xg)), int(runs))
        else:
            xp.random.seed(self.seed or 42)
            home = xp.random.poisson(max(0.05, float(home_xg)), int(runs))
            away = xp.random.poisson(max(0.05, float(away_xg)), int(runs))
        total = home + away
        def mean_bool(arr):
            val = xp.mean(arr.astype(float))
            return float(val.get() if hasattr(val, "get") else val)
        def mean_num(arr):
            val = xp.mean(arr)
            return float(val.get() if hasattr(val, "get") else val)
        res = MonteCarloResult(
            runs=int(runs), backend=self.backend,
            home_win=round(mean_bool(home > away), 6),
            draw=round(mean_bool(home == away), 6),
            away_win=round(mean_bool(away > home), 6),
            over_05=round(mean_bool(total > 0.5), 6),
            over_15=round(mean_bool(total > 1.5), 6),
            over_25=round(mean_bool(total > 2.5), 6),
            over_35=round(mean_bool(total > 3.5), 6),
            over_45=round(mean_bool(total > 4.5), 6),
            btts_yes=round(mean_bool((home > 0) & (away > 0)), 6),
            expected_home_goals=round(mean_num(home), 4),
            expected_away_goals=round(mean_num(away), 4),
        )
        return res.to_dict()
