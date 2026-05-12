from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .utils import clamp, num


class MetaModelAIV5:
    """Combines independent model outputs into final probability.

    Inputs may include simulation probability, ML adjustment, historical
    calibration and live intelligence. Market odds are deliberately excluded.
    """

    def __init__(self, data_dir: str | Path = "data/rocket_v5"):
        self.path = Path(data_dir) / "models" / "meta_model_v5.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"weights": {"simulation": 0.70, "ml": 0.12, "calibration": 0.10, "live": 0.08}, "segment_bias": {}}

    def save(self) -> None:
        self.path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")

    def segment_key(self, league: str, market: str) -> str:
        return f"{league or 'GLOBAL'}::{market}"

    def combine(self, *, simulation_prob: float, ml_adjustment: float = 0.0, calibration_adjustment: float = 0.0,
                live_adjustment: float = 0.0, league: str = "GLOBAL", market: str = "UNKNOWN",
                data_quality: float = 0.5) -> Dict[str, Any]:
        w = self.state.get("weights", {})
        raw = num(simulation_prob, 0.5)
        adjustment = (
            num(w.get("ml"), 0.12) * num(ml_adjustment)
            + num(w.get("calibration"), 0.10) * num(calibration_adjustment)
            + num(w.get("live"), 0.08) * num(live_adjustment)
        )
        bias = num(self.state.get("segment_bias", {}).get(self.segment_key(league, market)), 0.0)
        quality_shrink = 1 - clamp(num(data_quality, 0.5), 0.0, 1.0)
        final = raw + adjustment + bias
        final = final * (1 - 0.18 * quality_shrink) + 0.50 * (0.18 * quality_shrink)
        return {
            "probability": round(clamp(final, 0.01, 0.99), 6),
            "raw_probability": round(raw, 6),
            "total_adjustment": round(adjustment + bias, 6),
            "data_quality_shrink": round(quality_shrink, 4),
            "weights": w,
        }

    def update_segment_bias(self, league: str, market: str, predicted_prob: float, won: bool, lr: float = 0.008) -> None:
        key = self.segment_key(league, market)
        err = (1.0 if won else 0.0) - num(predicted_prob, 0.5)
        current = num(self.state.setdefault("segment_bias", {}).get(key), 0.0)
        self.state["segment_bias"][key] = round(clamp(current + lr * err, -0.08, 0.08), 6)
        self.save()
