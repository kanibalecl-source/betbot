"""Periodic runner for controlled QUALITY SHADOW candidate training."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

from quality_auto_retraining import ControlledQualityRetrainer


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def main() -> None:
    check_minutes = max(15, _int_env("BETBOT_QUALITY_RETRAIN_CHECK_MINUTES", 60))
    retrainer = ControlledQualityRetrainer(
        min_new_rows=_int_env("BETBOT_QUALITY_RETRAIN_MIN_NEW_ROWS", 300),
        min_hours=_int_env("BETBOT_QUALITY_RETRAIN_MIN_HOURS", 24),
        min_brier_improvement=float(
            os.getenv("BETBOT_QUALITY_RETRAIN_MIN_BRIER_IMPROVEMENT", "0.0002")
        ),
        min_log_loss_improvement=float(
            os.getenv("BETBOT_QUALITY_RETRAIN_MIN_LOGLOSS_IMPROVEMENT", "0.0002")
        ),
    )
    print(
        "QUALITY AUTO RETRAINING START "
        f"check={check_minutes}m min_new_rows={retrainer.min_new_rows} "
        f"min_hours={retrainer.min_hours} auto_promotion=false",
        flush=True,
    )
    while True:
        try:
            from storage_safety_monitor import check_storage_health
            storage = check_storage_health()
            print("STORAGE SAFETY " + json.dumps(storage, ensure_ascii=False), flush=True)
            from external_backup_export import run_external_backup_if_due
            external = run_external_backup_if_due()
            print("EXTERNAL BACKUP " + json.dumps(external, ensure_ascii=False), flush=True)
            result = retrainer.run()
            print(
                f"[{datetime.now(timezone.utc).isoformat()}] QUALITY RETRAINING "
                + json.dumps(result, ensure_ascii=False),
                flush=True,
            )
        except Exception as exc:
            print(f"QUALITY RETRAINING ERROR: {exc}", flush=True)
        time.sleep(check_minutes * 60)


if __name__ == "__main__":
    main()
