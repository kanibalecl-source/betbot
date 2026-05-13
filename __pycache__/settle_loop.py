import os
import time
from datetime import datetime

from settle_results import settle_open_bets


def get_loop_minutes():
    try:
        return int(os.getenv("SETTLE_LOOP_MINUTES", "180"))
    except Exception:
        return 180


def main():
    loop_minutes = get_loop_minutes()
    print(f"SETTLE LOOP START — co {loop_minutes} minut")

    while True:
        try:
            print(f"\n[{datetime.now()}] Sprawdzam wyniki")
            updated = settle_open_bets()
            print(f"Rozliczono: {updated}")
        except Exception as exc:
            print(f"[BŁĄD SETTLE LOOP] {exc}")

        time.sleep(loop_minutes * 60)


if __name__ == "__main__":
    main()
