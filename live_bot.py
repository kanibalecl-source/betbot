print("🚀 LIVE BOT FILE START")

import time
from datetime import datetime

print("✅ IMPORT TIME OK")

try:
    from live_engine import run_live
    print("✅ IMPORT LIVE_ENGINE OK")

except Exception as e:
    print(f"❌ IMPORT ERROR: {e}")
    raise


def main():
    print("🚀 LIVE ENGINE START")
    print(datetime.now())

    while True:
        try:
            print("⚽ START LIVE LOOP")

            run_live()

            print("✅ LIVE LOOP COMPLETE")

        except Exception as e:
            print(f"❌ LIVE ERROR: {e}")

        print("⏳ Sleep 60s")
        time.sleep(60)


if __name__ == "__main__":
    main()
