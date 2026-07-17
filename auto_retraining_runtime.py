from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from advanced_calibration_analytics import AdvancedCalibrationAnalytics
from ml_training_pipeline import MLTrainingPipeline
from walk_forward_lab import WalkForwardLab
from storage_paths import DATA_DIR


class AutoRetrainingRuntime:
    """Nightly/periodic retraining runtime with state file and reports."""

    def __init__(self, data_dir: str | Path | None = None, min_hours_between_runs: int = 12):
        self.data_dir = Path(data_dir) if data_dir is not None else DATA_DIR / "enterprise"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.data_dir / "auto_retraining_state.json"
        self.min_hours_between_runs = min_hours_between_runs
        self.state = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.state_path.exists():
            try: return json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception: pass
        return {"last_run": None, "runs": 0, "status": "READY"}

    def _save(self):
        self.state_path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")

    def due(self) -> bool:
        raw = self.state.get("last_run")
        if not raw: return True
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) - dt >= timedelta(hours=self.min_hours_between_runs)
        except Exception:
            return True

    def nightly_retrain(self, force: bool = False) -> Dict[str, Any]:
        if not force and not self.due():
            return {"status": "SKIPPED_NOT_DUE", **self.state}
        started = datetime.now(timezone.utc).isoformat()
        ml = MLTrainingPipeline(self.data_dir)
        rows = ml.load_rows_from_csv()
        train = ml.train(rows)
        cal = AdvancedCalibrationAnalytics(self.data_dir).calibrate(rows)
        wf = WalkForwardLab(self.data_dir).run(rows)
        self.state.update({
            "last_run": datetime.now(timezone.utc).isoformat(),
            "runs": int(self.state.get("runs",0))+1,
            "status": "DONE",
            "started_at": started,
            "training_status": train.get("status"),
            "walk_forward_status": wf.get("status"),
            "samples": train.get("samples", 0),
        })
        self._save()
        return {"status": "RETRAINING_EXECUTED", "training": train, "calibration": cal, "walk_forward": wf, "state": self.state}

    def run_if_due(self) -> Dict[str, Any]:
        return self.nightly_retrain(force=False)
