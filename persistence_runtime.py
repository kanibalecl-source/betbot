from __future__ import annotations

import time
from datetime import datetime

from agi_storage import sync_picks_from_csv
from result_updater_unified import settle_stored_picks


def run_once() -> dict:
    sync = sync_picks_from_csv()
    settle = settle_stored_picks()
    return {"sync": sync, "settle": settle}


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
