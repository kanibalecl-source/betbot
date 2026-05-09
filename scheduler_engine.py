import os
import subprocess
import time
import traceback
from datetime import datetime

print("🚨 SCHEDULER FILE STARTED")


BOT_FILE = "main.py"


def run_bot():
    print("🚀 STARTING LIVE BOT")
    print(f"⏰ {datetime.now()}")

    process = subprocess.Popen(
        ["python3", BOT_FILE],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    return process


def stream_logs(process):
    while True:
        line = process.stdout.readline()

        if not line:
            break

        print(line.strip())


def main():
    while True:
        try:
            print("📡 FETCH LOOP START")

            process = run_bot()

            stream_logs(process)

            return_code = process.wait()

            print(f"❌ BOT STOPPED | CODE={return_code}")

        except Exception as e:
            print(f"❌ SCHEDULER ERROR: {e}")
            traceback.print_exc()

        print("🔁 RESTART IN 15 SEC")

        time.sleep(15)


if __name__ == "__main__":
    main()
