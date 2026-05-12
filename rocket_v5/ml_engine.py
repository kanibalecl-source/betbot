from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .utils import clamp, num, sigmoid


@dataclass
class MLTrainingReport:
    samples: int
    features: List[str]
    model_path: str
    note: str


class LightweightMLEngineV5:
    """Dependency-light ML layer.

    Uses sklearn LogisticRegression if available. If not, it falls back to a
    transparent linear model with online SGD-style updates. Designed to be safe
    in minimal hosting environments.
    """

    DEFAULT_FEATURES = [
        "home_xg", "away_xg", "xg_diff", "total_xg", "data_quality",
        "home_form", "away_form", "tempo", "lineup_delta", "fatigue_delta",
    ]

    def __init__(self, data_dir: str | Path = "data/rocket_v5"):
        self.data_dir = Path(data_dir)
        self.model_dir = self.data_dir / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.model_dir / "lightweight_ml_v5.json"
        self.state = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"features": self.DEFAULT_FEATURES, "weights": {f: 0.0 for f in self.DEFAULT_FEATURES}, "bias": 0.0, "trained_samples": 0}

    def save(self) -> None:
        self.path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")

    def build_features(self, match: Dict[str, Any], xg: Dict[str, Any]) -> Dict[str, float]:
        hxg = num(xg.get("home_xg"), 1.2)
        axg = num(xg.get("away_xg"), 1.0)
        return {
            "home_xg": hxg,
            "away_xg": axg,
            "xg_diff": hxg - axg,
            "total_xg": hxg + axg,
            "data_quality": num(xg.get("data_quality"), num(match.get("data_quality"), 0.5)),
            "home_form": num(match.get("home_form"), 0.0),
            "away_form": num(match.get("away_form"), 0.0),
            "tempo": num(match.get("tempo"), num(match.get("tactical_openness"), 1.0)),
            "lineup_delta": num(match.get("home_lineup_strength"), 1.0) - num(match.get("away_lineup_strength"), 1.0),
            "fatigue_delta": num(match.get("away_fatigue"), 0.0) - num(match.get("home_fatigue"), 0.0),
        }

    def predict_adjustment(self, features: Dict[str, float]) -> float:
        z = num(self.state.get("bias"), 0.0)
        weights = self.state.get("weights", {})
        for f in self.state.get("features", self.DEFAULT_FEATURES):
            z += num(weights.get(f), 0.0) * num(features.get(f), 0.0)
        # returns conservative probability adjustment around 0
        return clamp((sigmoid(z) - 0.5) * 0.16, -0.08, 0.08)

    def train_online(self, rows: Iterable[Dict[str, Any]], target_field: str = "won", lr: float = 0.015) -> MLTrainingReport:
        features = self.state.get("features", self.DEFAULT_FEATURES)
        weights = self.state.setdefault("weights", {f: 0.0 for f in features})
        samples = 0
        for row in rows:
            y = 1.0 if row.get(target_field) in (1, True, "WON", "won") else 0.0
            x = {f: num(row.get(f), 0.0) for f in features}
            z = num(self.state.get("bias"), 0.0) + sum(num(weights.get(f), 0.0) * x[f] for f in features)
            p = sigmoid(z)
            error = y - p
            self.state["bias"] = num(self.state.get("bias"), 0.0) + lr * error
            for f in features:
                weights[f] = num(weights.get(f), 0.0) + lr * error * x[f]
            samples += 1
        self.state["trained_samples"] = int(self.state.get("trained_samples", 0)) + samples
        self.save()
        return MLTrainingReport(samples, features, str(self.path), "online lightweight model updated")
