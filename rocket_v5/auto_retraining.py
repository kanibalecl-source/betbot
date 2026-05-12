from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from .ml_engine import LightweightMLEngineV5
from .meta_model import MetaModelAIV5
from .utils import num


class AutoRetrainingEngineV5:
    def __init__(self, data_dir: str | Path = "data/rocket_v5"):
        self.data_dir = Path(data_dir)
        self.settlement_file = self.data_dir / "settlement" / "settled_bets_v5.csv"
        self.report_dir = self.data_dir / "reports"
        self.settlement_file.parent.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.ml = LightweightMLEngineV5(self.data_dir)
        self.meta = MetaModelAIV5(self.data_dir)

    def load_settled(self) -> List[Dict[str, Any]]:
        if not self.settlement_file.exists():
            return []
        with self.settlement_file.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def nightly_retrain(self) -> Dict[str, Any]:
        rows = self.load_settled()
        training_rows = []
        for r in rows:
            training_rows.append({
                "won": r.get("status") == "WON" or r.get("won") in ("1", "true", True),
                "home_xg": num(r.get("home_xg")), "away_xg": num(r.get("away_xg")),
                "xg_diff": num(r.get("home_xg")) - num(r.get("away_xg")),
                "total_xg": num(r.get("home_xg")) + num(r.get("away_xg")),
                "data_quality": num(r.get("data_quality"), 0.5),
                "home_form": num(r.get("home_form")), "away_form": num(r.get("away_form")),
                "tempo": num(r.get("tempo"), 1.0), "lineup_delta": num(r.get("lineup_delta")),
                "fatigue_delta": num(r.get("fatigue_delta")),
            })
            if r.get("league") and r.get("market") and r.get("probability"):
                self.meta.update_segment_bias(r.get("league"), r.get("market"), num(r.get("probability"), 0.5), training_rows[-1]["won"])
        ml_report = self.ml.train_online(training_rows) if training_rows else None
        report = {
            "settled_rows": len(rows),
            "training_rows": len(training_rows),
            "ml_report": asdict(ml_report) if ml_report else None,
            "meta_model_path": str(self.meta.path),
        }
        out = self.report_dir / "nightly_retrain_report_v5.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
