"""Supervised v8 quality loop: retraining, model, evidence and capital gates."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

from autonomous_learning_governor import AutonomousLearningGovernor
from quality_auto_retraining import ControlledQualityRetrainer
from staged_capital_governor import StagedCapitalGovernor
from statistical_evidence_scorecard import StatisticalEvidenceScorecard


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def main() -> None:
    minutes = max(15, _int("BETBOT_GOVERNOR_CHECK_MINUTES", 60))
    retrainer = ControlledQualityRetrainer(
        min_new_rows=_int("BETBOT_QUALITY_RETRAIN_MIN_NEW_ROWS", 300),
        min_hours=_int("BETBOT_QUALITY_RETRAIN_MIN_HOURS", 24),
    )
    model_governor = AutonomousLearningGovernor()
    scorecard = StatisticalEvidenceScorecard()
    capital_governor = StagedCapitalGovernor()
    print(f"QUALITY GOVERNANCE V8 START check={minutes}m", flush=True)
    while True:
        try:
            result = {
                "retraining": retrainer.run(),
                "model_governor": model_governor.run(),
                "evidence_scorecard": scorecard.run(),
                "capital_governor": capital_governor.run(),
            }
            print(
                f"[{datetime.now(timezone.utc).isoformat()}] QUALITY GOVERNANCE V8 "
                + json.dumps(result, ensure_ascii=False),
                flush=True,
            )
        except Exception as exc:
            print(f"QUALITY GOVERNANCE V8 ERROR: {exc}", flush=True)
        time.sleep(minutes * 60)


if __name__ == "__main__":
    main()
