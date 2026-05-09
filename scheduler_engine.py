import subprocess
import time
import traceback
from datetime import datetime

print("🚨 SCHEDULER FILE STARTED")


def run_prematch():
    while True:
        try:
            print("🚀 START PREMATCH BOT")
            print(f"⏰ {datetime.now()}")

            print("📡 FETCHING MATCHES")

            result = subprocess.run(
                ["python3", "bot.py"],
                capture_output=True,
                text=True
            )

            print("✅ BOT EXECUTED")

            if result.stdout:
                print("📄 STDOUT:")
                print(result.stdout)

            if result.stderr:
                print("❌ STDERR:")
                print(result.stderr)

            print("✅ LIVE SAVED")
            print("💓 SCHEDULER LOOP OK")

        except Exception as e:
            print(f"❌ BŁĄD PREMATCH: {e}")
            traceback.print_exc()

        print("⏳ Kolejne uruchomienie za 5 minut")

        time.sleep(300)


def main():
    print("🚀 BETBOT PRODUCTION SCHEDULER")
    print(f"⏰ {datetime.now()}")

    run_prematch()


if __name__ == "__main__":
    main()
