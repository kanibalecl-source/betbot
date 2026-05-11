from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional, Any

from .config import RocketConfig, load_config
from .probability import normalize_probability


class LearningEngineV4:
    """Persistent lightweight calibration engine.

    Learns per league+market bias from settled bets. This is intentionally
    conservative: it adjusts probabilities slowly to avoid overfitting.
    """

    def __init__(self, config: Optional[RocketConfig] = None):
        self.config = config or load_config()
        self.path = self.config.data_dir / "models" / "calibration_v4.json"
        self.state = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"segments": {}, "global": {"n": 0, "bias": 0.0}}

    def save(self) -> None:
        self.path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")

    def key(self, league: str, market: str) -> str:
        return f"{league or 'UNKNOWN'}::{market or 'UNKNOWN'}"

    def calibrate(self, probability: float, league: str, market: str) -> float:
        p = normalize_probability(probability)
        if p is None:
            return None
        seg = self.state["segments"].get(self.key(league, market), {})
        bias = float(seg.get("bias", 0.0))
        n = int(seg.get("n", 0))
        # Trust segment slowly; cap influence until sample is large.
        strength = min(1.0, n / 250.0)
        adjusted = p + bias * strength
        return round(max(0.01, min(0.99, adjusted)), 6)

    def update_from_settlement(self, pick: Dict[str, Any]) -> None:
        p = normalize_probability(pick.get("model_probability"))
        won = pick.get("status") == "WON" or pick.get("won") is True
        if p is None or pick.get("status") not in {"WON", "LOST"} and "won" not in pick:
            return
        y = 1.0 if won else 0.0
        league = str(pick.get("league", "UNKNOWN"))
        market = str(pick.get("market", "UNKNOWN"))
        k = self.key(league, market)
        seg = self.state["segments"].setdefault(k, {"n": 0, "bias": 0.0, "brier": 0.0})
        n = int(seg["n"])
        err = y - p
        lr = 0.035 / ((n + 25) ** 0.35)
        seg["bias"] = round(max(-0.12, min(0.12, float(seg["bias"]) + lr * err)), 6)
        seg["brier"] = round(((float(seg.get("brier", 0))*n) + (p-y)**2) / (n+1), 6)
        seg["n"] = n + 1
        self.state["global"]["n"] = int(self.state["global"].get("n", 0)) + 1
        self.save()
