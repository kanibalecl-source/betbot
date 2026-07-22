from __future__ import annotations

import time
from datetime import datetime

from agi_storage import sync_picks_from_csv
from result_updater_unified import (
    capture_closing_odds_for_open_picks,
    capture_scheduled_odds_for_open_picks,
    settle_stored_picks,
)

try:
    from betbot.storage.append_only_history import append_event
except Exception:
    def append_event(*args, **kwargs):
        return None


def run_once() -> dict:
    sync = sync_picks_from_csv()
    scheduled = capture_scheduled_odds_for_open_picks()
    closing = capture_closing_odds_for_open_picks()
    settle = settle_stored_picks()
    try:
        from shadow_feature_collector import collect_shadow_features
        shadow_features = collect_shadow_features()
    except Exception as exc:
        shadow_features = {"status": "ERROR", "error": str(exc)}
    try:
        from quality_data_guardian import run_guardian
        guardian = run_guardian()
    except Exception as exc:
        guardian = {"status": "ERROR", "error": str(exc)}
    result = {
        "sync": sync, "scheduled_odds": scheduled, "closing_odds": closing,
        "settle": settle, "shadow_features": shadow_features, "guardian": guardian,
    }
    append_event("persistence_cycles", result, source="persistence_runtime.py")
    return result


def main() -> None:
    print("AGI PERSISTENCE RUNTIME START")
    while True:
        try:
            result = run_once()
            print(f"[{datetime.now()}] persistence ok: {result}")
        except Exception as exc:
            print(f"PERSISTENCE ERROR: {exc}")
        time.sleep(300)


if __name__ == "__main__":
    main()
