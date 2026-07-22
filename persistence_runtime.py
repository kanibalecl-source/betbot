from __future__ import annotations

import time
from datetime import datetime

from agi_storage import sync_picks_from_csv
from result_updater_unified import capture_closing_odds_for_open_picks, settle_stored_picks

try:
    from betbot.storage.append_only_history import append_event
except Exception:
    def append_event(*args, **kwargs):
        return None


def run_once() -> dict:
    sync = sync_picks_from_csv()
    closing = capture_closing_odds_for_open_picks()
    settle = settle_stored_picks()
    result = {"sync": sync, "closing_odds": closing, "settle": settle}
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
