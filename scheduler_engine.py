import subprocess
import time
from datetime import datetime


def run_prematch():
    while True:
        try:
            print("🚀 START PREMATCH BOT")

            result = subprocess.run(
                ["python", "bot.py"],
                capture_output=True,
                text=True
            )

            print(result.stdout)

            if result.stderr:
                print("❌ STDERR:")
                print(result.stderr)

        except Exception as e:
            print(f"❌ BŁĄD PREMATCH: {e}")

        print("⏳ Kolejne uruchomienie za 5 minut")
        time.sleep(300)


def main():
    print("🚀 BETBOT PRODUCTION SCHEDULER")
    print(f"⏰ {datetime.now()}")

    run_prematch()


if __name__ == "__main__":
    main()
