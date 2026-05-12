from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

from ml_training_pipeline import MLTrainingPipeline


def _num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "": return default
        return float(v)
    except Exception:
        return default


def _target(row: Dict[str, Any]) -> int:
    return 1 if row.get("won", row.get("result", row.get("outcome", row.get("status")))) in (1, True, "1", "WON", "won", "WIN", "win") else 0


@dataclass
class WalkForwardReport:
    status: str
    folds: int
    samples: int
    roi: float
    hit_rate: float
    brier_score: float
    max_drawdown: float
    details: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]: return asdict(self)


class WalkForwardLab:
    """Rolling walk-forward validation lab for model honesty."""

    def __init__(self, data_dir: str | Path = "data/enterprise"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.report_path = self.data_dir / "walk_forward_report.json"

    def run(self, rows: Iterable[Dict[str, Any]] | None = None, train_size: int = 80, test_size: int = 20) -> Dict[str, Any]:
        if rows is None:
            rows = MLTrainingPipeline(self.data_dir).load_rows_from_csv()
        rows = [r for r in rows if any(k in r for k in ("won", "result", "outcome", "status"))]
        if len(rows) < max(10, test_size):
            report = WalkForwardReport("NO_ENOUGH_DATA", 0, len(rows), 0.0, 0.0, 0.0, 0.0, [])
            self.report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            return report.to_dict()
        details=[]; profits=[]; briers=[]; hits=0; n=0
        start = 0
        while start + max(5, train_size//2) < len(rows):
            train = rows[start:start+train_size]
            test = rows[start+train_size:start+train_size+test_size]
            if not test: break
            model = MLTrainingPipeline(self.data_dir / f"fold_{len(details)+1}")
            train_report = model.train(train, epochs=5)
            fold_profit=0.0; fold_brier=0.0; fold_hits=0
            for r in test:
                p=model.predict_proba(r)
                y=_target(r)
                odds=_num(r.get("odds"),2.0)
                stake=_num(r.get("stake"),1.0) or 1.0
                profit = stake*(odds-1) if y else -stake
                fold_profit += profit
                fold_brier += (p-y)**2
                fold_hits += int((p>=0.5)==bool(y))
                profits.append(profit); briers.append((p-y)**2); hits += int((p>=0.5)==bool(y)); n+=1
            details.append({"fold": len(details)+1, "train_samples": len(train), "test_samples": len(test), "profit": round(fold_profit,4), "hit_rate": round(fold_hits/len(test),4), "brier": round(fold_brier/len(test),6), "train_status": train_report.get("status")})
            start += test_size
        roi = sum(profits)/max(1, sum(abs(_num(r.get("stake"),1.0) or 1.0) for r in rows[:len(profits)]))
        equity=0.0; peak=0.0; max_dd=0.0
        for p in profits:
            equity += p; peak=max(peak,equity); max_dd=max(max_dd, peak-equity)
        report=WalkForwardReport("COMPLETE", len(details), n, round(roi,6), round(hits/max(1,n),6), round(sum(briers)/max(1,len(briers)),6), round(max_dd,4), details)
        self.report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return report.to_dict()
