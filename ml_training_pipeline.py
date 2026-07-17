from __future__ import annotations

import csv
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from advanced_calibration_analytics import AdvancedCalibrationAnalytics
from storage_paths import DATA_DIR


def _num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "": return default
        return float(v)
    except Exception:
        return default


def _sigmoid(x: float) -> float:
    import math
    if x < -35: return 0.0
    if x > 35: return 1.0
    return 1.0/(1.0+math.exp(-x))


@dataclass
class TrainingReport:
    status: str
    samples: int
    features: List[str]
    model_path: str
    calibration: Dict[str, Any]
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MLTrainingPipeline:
    """Dependency-light real ML training pipeline.

    It trains a logistic online model from settled betting history. It is built
    for minimal hosts where sklearn/xgboost may not be installed, but it still
    performs real optimization, stores weights and serves inference.
    """

    # Pola dostępne w kanonicznej, rozliczonej historii. Nie uczymy modelu na
    # sztucznie uzupełnianym xG, formie, tempie ani jakości danych.
    DEFAULT_FEATURES = ["probability", "odds", "edge", "ev", "confidence"]

    def __init__(self, data_dir: str | Path = "data/enterprise", model_name: str = "v7_logistic"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.data_dir / f"{model_name}.json"
        self.report_path = self.data_dir / f"{model_name}_training_report.json"
        self.calibration = AdvancedCalibrationAnalytics(self.data_dir)
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if self.model_path.exists():
            try:
                state = json.loads(self.model_path.read_text(encoding="utf-8"))
                if state.get("version") == 2 and state.get("features") == self.DEFAULT_FEATURES:
                    return state
                backup = self.model_path.with_name(f"{self.model_path.stem}_legacy_unverified_v1.json")
                if not backup.exists():
                    backup.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
        return {"features": self.DEFAULT_FEATURES, "weights": {f: 0.0 for f in self.DEFAULT_FEATURES}, "bias": 0.0, "trained_samples": 0, "version": 2}

    def _save(self) -> None:
        self.model_path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_rows_from_csv(self, paths: Optional[List[str | Path]] = None) -> List[Dict[str, Any]]:
        paths = paths or [DATA_DIR / "results_history.csv"]
        rows: List[Dict[str, Any]] = []
        for path in paths:
            p = Path(path)
            if not p.is_absolute(): p = Path.cwd() / p
            if not p.exists(): continue
            try:
                with p.open("r", encoding="utf-8", newline="") as fh:
                    rows.extend(list(csv.DictReader(fh)))
            except Exception:
                continue
        return rows

    def train(self, rows: Optional[Iterable[Dict[str, Any]]] = None, epochs: int = 8, lr: float = 0.018) -> Dict[str, Any]:
        rows = list(rows) if rows is not None else self.load_rows_from_csv()
        clean = [self._normalize_row(r) for r in rows if self._has_target(r) and self._has_features(r)]
        if not clean:
            report = TrainingReport("NO_SETTLED_DATA", 0, self.state["features"], str(self.model_path), {}, {"note": "Add settled bets with won/result/outcome field."})
            self.report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            return report.to_dict()
        features = self.state["features"]
        weights = self.state.setdefault("weights", {f: 0.0 for f in features})
        bias = _num(self.state.get("bias"), 0.0)
        for _ in range(max(1, int(epochs))):
            for r in clean:
                y = r["target"]
                z = bias + sum(_num(weights.get(f), 0.0) * _num(r.get(f), 0.0) for f in features)
                p = _sigmoid(z)
                err = y - p
                bias += lr * err
                for f in features:
                    # small L2 regularization keeps model stable on tiny samples
                    weights[f] = _num(weights.get(f), 0.0) + lr * (err * _num(r.get(f), 0.0) - 0.0008 * _num(weights.get(f), 0.0))
        self.state["bias"] = bias
        self.state["trained_samples"] = int(self.state.get("trained_samples", 0)) + len(clean)
        self.state["version"] = 2
        self.state["training_runs"] = int(self.state.get("training_runs", 0)) + 1
        self._save()
        preds = [self.predict_proba(r) for r in clean]
        brier = sum((p-r["target"])**2 for p,r in zip(preds, clean))/len(clean)
        accuracy = sum((p>=0.5)==(r["target"]>=0.5) for p,r in zip(preds, clean))/len(clean)
        cal = self.calibration.calibrate([{**r, "probability": p, "won": bool(r["target"])} for p,r in zip(preds, clean)])
        report = TrainingReport("TRAINED", len(clean), features, str(self.model_path), cal, {"brier_score": round(brier,6), "accuracy": round(accuracy,6)})
        self.report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return report.to_dict()

    def predict_proba(self, row: Dict[str, Any]) -> float:
        r = self._normalize_row(row, require_target=False)
        z = _num(self.state.get("bias"), 0.0) + sum(_num(self.state.get("weights", {}).get(f), 0.0)*_num(r.get(f), 0.0) for f in self.state.get("features", self.DEFAULT_FEATURES))
        return round(max(0.01, min(0.99, _sigmoid(z))), 6)

    def _has_target(self, r: Dict[str, Any]) -> bool:
        val = r.get("won", r.get("result", r.get("outcome")))
        return str(val).strip().upper() in {"1", "0", "TRUE", "FALSE", "WIN", "WON", "LOSE", "LOSS", "LOST"}

    def _has_features(self, r: Dict[str, Any]) -> bool:
        probability = r.get("probability", r.get("model_prob", r.get("predicted_prob")))
        odds = r.get("odds", r.get("bookmaker_odds"))
        try:
            return probability not in (None, "") and odds not in (None, "") and float(odds) > 1
        except Exception:
            return False

    def _normalize_row(self, r: Dict[str, Any], require_target: bool = True) -> Dict[str, Any]:
        probability = _num(r.get("probability", r.get("model_prob", r.get("predicted_prob"))), 0.0)
        out = {
            "probability": probability,
            "odds": _num(r.get("odds", r.get("bookmaker_odds")), 0.0),
            "edge": _num(r.get("edge", r.get("model_edge")), 0.0),
            "ev": _num(r.get("ev", r.get("expected_value")), 0.0),
            "confidence": _num(r.get("confidence"), probability),
            "market": str(r.get("market", "ALL")),
            "league": str(r.get("league", "ALL")),
        }
        if require_target:
            val = r.get("won", r.get("result", r.get("outcome", r.get("status"))))
            out["target"] = 1.0 if val in (1, True, "1", "WON", "won", "WIN", "win") else 0.0
        return out
