import subprocess
import time
import traceback
import sys
from datetime import datetime

print("🚨 SCHEDULER FILE STARTED")

sys.stdout.flush()


def run_prematch():
    while True:
        try:
            print("🚀 START PREMATCH BOT")
            print(f"⏰ {datetime.now()}")

            sys.stdout.flush()

            print("📡 FETCHING MATCHES")

            sys.stdout.flush()

            process = subprocess.Popen(
                ["python3", "bot.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            while True:
                output = process.stdout.readline()

                if output == "" and process.poll() is not None:
                    break

                if output:
                    print(f"[BOT] {output.strip()}")

                    sys.stdout.flush()

            return_code = process.poll()

            print(f"✅ BOT EXECUTED | CODE={return_code}")

            sys.stdout.flush()

            try:
                from live_pipeline_runtime import run_once as run_live_pipeline_once
                live_count = run_live_pipeline_once()
                print(f"✅ LIVE SCHEDULER PIPELINE OK | active={live_count}")
            except Exception as live_error:
                print(f"❌ LIVE SCHEDULER PIPELINE ERROR: {live_error}")

            print("✅ LIVE SAVED")
            print("💓 SCHEDULER LOOP OK")

            sys.stdout.flush()

        except Exception as e:
            print(f"❌ BŁĄD PREMATCH: {e}")

            traceback.print_exc()

            sys.stdout.flush()

        print("⏳ Kolejne uruchomienie za 5 minut")

        sys.stdout.flush()

        time.sleep(300)


def main():
    print("🚀 BETBOT PRODUCTION SCHEDULER")
    print(f"⏰ {datetime.now()}")

    sys.stdout.flush()

    run_prematch()


if __name__ == "__main__":
    main()


# === AUTONOMOUS AI BOOTSTRAP ===
try:
    from ai_autonomous_runtime import bootstrap_ai_picks
    bootstrap_ai_picks()
    print("[AI] autonomous bootstrap active")
except Exception as e:
    print("[AI] bootstrap error:", e)

