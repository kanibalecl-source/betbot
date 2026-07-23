"""Supervised periodic runner for retraining and Autonomous Governor v7."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

from autonomous_learning_governor import AutonomousLearningGovernor
from quality_auto_retraining import ControlledQualityRetrainer


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
    governor = AutonomousLearningGovernor()
    print(f"AUTONOMOUS LEARNING GOVERNOR V7 START check={minutes}m", flush=True)
    while True:
        try:
            retraining = retrainer.run()
            decision = governor.run()
            print(
                f"[{datetime.now(timezone.utc).isoformat()}] GOVERNOR V7 "
                + json.dumps({"retraining": retraining, "decision": decision}, ensure_ascii=False),
                flush=True,
            )
        except Exception as exc:
            print(f"AUTONOMOUS GOVERNOR V7 ERROR: {exc}", flush=True)
        time.sleep(minutes * 60)


if __name__ == "__main__":
    main()
