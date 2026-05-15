from __future__ import annotations

import os
import time
from datetime import datetime

from auto_retraining_runtime import AutoRetrainingRuntime


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def main() -> None:
    check_minutes = _int_env("RETRAIN_CHECK_MINUTES", 60)
    min_hours = _int_env("RETRAIN_MIN_HOURS", 12)
    runtime = AutoRetrainingRuntime(data_dir="data/enterprise", min_hours_between_runs=min_hours)
    print(f"🚀 AUTO RETRAINING LOOP START | check={check_minutes}m | min_hours={min_hours}")

    while True:
        try:
            print(f"[{datetime.now()}] AUTO RETRAINING CHECK")
            result = runtime.run_if_due()
            print(f"✅ AUTO RETRAINING RESULT | {result.get('status')} | runs={result.get('runs', result.get('state', {}).get('runs', 0))}")
        except Exception as exc:
            print(f"❌ AUTO RETRAINING LOOP ERROR: {exc}")
        time.sleep(max(5, check_minutes) * 60)


if __name__ == "__main__":
    main()
