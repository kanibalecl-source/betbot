import os
import time
from datetime import datetime

from bot import run_bot


def get_loop_minutes():
    try:
        return int(os.getenv("BOT_LOOP_MINUTES", "120"))
    except Exception:
        return 120


def main():
    loop_minutes = get_loop_minutes()
    print(f"BOT LOOP START — co {loop_minutes} minut")

    while True:
        try:
            print(f"\n[{datetime.now()}] Uruchamiam bot.py")
            run_bot()
        except Exception as exc:
            print(f"[BŁĄD BOT LOOP] {exc}")

        time.sleep(loop_minutes * 60)


if __name__ == "__main__":
    main()
