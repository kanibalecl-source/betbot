import subprocess
import time
import traceback
from datetime import datetime

print("✅ scheduler_engine.py STARTED")


def run_live_bot():
    print("🚀 STARTING LIVE BOT")
    print(f"⏰ {datetime.now()}")

    process = subprocess.Popen(
        ["python3", "main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    while True:
        output = process.stdout.readline()

        if output == "" and process.poll() is not None:
            break

        if output:
            print(output.strip())

    return_code = process.poll()

    print(f"❌ LIVE BOT STOPPED | CODE={return_code}")


def main():
    while True:
        try:
            print("📡 FETCH LOOP START")

            run_live_bot()

        except Exception as e:
            print(f"❌ SCHEDULER ERROR: {e}")

            traceback.print_exc()

        print("🔁 RESTART ZA 15 SEKUND")

        time.sleep(15)


if __name__ == "__main__":
    main()
