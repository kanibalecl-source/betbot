import time
from datetime import datetime

from live_engine import run_live


def main():
    print("🚀 LIVE ENGINE START")
    print(f"⏰ {datetime.now()}")

    while True:
        try:
            print("⚽ START LIVE LOOP")

            run_live()

            print("✅ LIVE LOOP COMPLETE")

        except Exception as e:
            print(f"❌ LIVE ENGINE ERROR: {e}")

        print("⏳ Kolejne LIVE sprawdzenie za 60 sekund")
        time.sleep(60)


if __name__ == "__main__":
    main()
