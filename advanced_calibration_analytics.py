from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


def _num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "": return default
        return float(v)
    except Exception:
        return default


def _clamp(x: float, lo: float = 0.01, hi: float = 0.99) -> float:
    return max(lo, min(hi, x))


@dataclass
class CalibrationReport:
    samples: int
    brier_score: float
    ece: float
    bins: List[Dict[str, float]]
    market: str
    league: str
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AdvancedCalibrationAnalytics:
    """Brier/ECE/reliability calibration with persistent per-segment offsets."""

    def __init__(self, data_dir: str | Path = "data/enterprise"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "calibration_state.json"
        self.state = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try: return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception: pass
        return {"segments": {}, "global_offset": 0.0}

    def save(self) -> None:
        self.path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")

    def calibrate(self, rows: Iterable[Dict[str, Any]], market: str = "ALL", league: str = "ALL", bins: int = 10) -> Dict[str, Any]:
        report = self.fit(rows, market=market, league=league, bins=bins)
        return report.to_dict()

    def fit(self, rows: Iterable[Dict[str, Any]], market: str = "ALL", league: str = "ALL", bins: int = 10) -> CalibrationReport:
        data = []
        for r in rows:
            if market != "ALL" and str(r.get("market")) != market: continue
            if league != "ALL" and str(r.get("league")) != league: continue
            p = _clamp(_num(r.get("probability", r.get("model_prob", r.get("predicted_prob"))), 0.5))
            y_raw = r.get("won", r.get("result", r.get("outcome")))
            y = 1.0 if y_raw in (1, True, "WON", "won", "WIN", "win") else 0.0
            data.append((p, y))
        if not data:
            return CalibrationReport(0, 0.0, 0.0, [], market, league, "NO_DATA")
        brier = sum((p-y)**2 for p,y in data)/len(data)
        bin_rows: List[Dict[str, float]] = []
        ece = 0.0
        offsets = []
        for i in range(bins):
            lo, hi = i/bins, (i+1)/bins
            chunk = [(p,y) for p,y in data if (p >= lo and (p < hi or i == bins-1))]
            if not chunk: continue
            conf = sum(p for p,_ in chunk)/len(chunk)
            acc = sum(y for _,y in chunk)/len(chunk)
            gap = acc-conf
            offsets.append(gap)
            ece += (len(chunk)/len(data))*abs(gap)
            bin_rows.append({"bin_low": round(lo,2), "bin_high": round(hi,2), "count": len(chunk), "avg_prob": round(conf,4), "actual": round(acc,4), "gap": round(gap,4)})
        offset = sum(offsets)/len(offsets) if offsets else 0.0
        key = self._key(market, league)
        self.state.setdefault("segments", {})[key] = {"offset": round(offset, 6), "samples": len(data), "brier_score": round(brier,6), "ece": round(ece,6)}
        if market == "ALL" and league == "ALL": self.state["global_offset"] = round(offset, 6)
        self.save()
        status = "CALIBRATED" if len(data) >= 30 else "CALIBRATED_LOW_SAMPLE"
        return CalibrationReport(len(data), round(brier,6), round(ece,6), bin_rows, market, league, status)

    def apply(self, probability: float, market: str = "ALL", league: str = "ALL") -> float:
        p = _clamp(float(probability))
        seg = self.state.get("segments", {}).get(self._key(market, league)) or self.state.get("segments", {}).get(self._key(market, "ALL"))
        offset = _num((seg or {}).get("offset"), _num(self.state.get("global_offset"), 0.0))
        # conservative application: never move more than 6 percentage points
        return round(_clamp(p + max(-0.06, min(0.06, offset))), 6)

    def _key(self, market: str, league: str) -> str:
        return f"{league}::{market}"
