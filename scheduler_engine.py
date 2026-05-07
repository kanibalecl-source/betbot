import threading
import time
from datetime import datetime

from bot_loop import main as prematch_loop
from live_bot import run_live


def safe_runner(name, target):
    while True:
        try:
            print(f"🚀 START MODUŁU: {name}")
            target()

        except Exception as e:
            print(f"❌ BŁĄD {name}: {e}")

        print(f"🔁 Restart modułu za 10 sekund: {name}")
        time.sleep(10)


def start_thread(name, target):
    thread = threading.Thread(
        target=safe_runner,
        args=(name, target),
        daemon=True
    )

    thread.start()

    print(f"✅ Thread aktywny: {name}")

    return thread


def main():
    print("🚀 FULL BETBOT SCHEDULER START")
    print(f"⏰ {datetime.now()}")

    # =========================
    # PREMATCH ENGINE
    # =========================

    start_thread("PREMATCH ENGINE", prematch_loop)

    # =========================
    # LIVE ENGINE
    # =========================

    start_thread("LIVE ENGINE", run_live)

    # =========================
    # KEEP ALIVE
    # =========================

    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
