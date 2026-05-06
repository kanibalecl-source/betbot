import threading
import time
from datetime import datetime

from bot_loop import main as prematch_loop
from live_bot import run_live
from settle_loop import main as settlement_loop


def start_thread(name, target):
    thread = threading.Thread(target=target, name=name, daemon=True)
    thread.start()
    print(f"✅ Uruchomiono moduł: {name}")
    return thread


def main():
    print("🚀 SCHEDULER ENGINE START")
    print(f"Start: {datetime.now()}")

    start_thread("PREMATCH LOOP", prematch_loop)
    start_thread("LIVE LOOP", run_live)
    start_thread("SETTLEMENT LOOP", settlement_loop)

    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
