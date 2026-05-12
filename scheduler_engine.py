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

            print("✅ LIVE SAVED")

            run_v7_enterprise_maintenance()
            print("💓 SCHEDULER LOOP OK")

            sys.stdout.flush()

        except Exception as e:
            print(f"❌ BŁĄD PREMATCH: {e}")

            traceback.print_exc()

            sys.stdout.flush()

        print("⏳ Kolejne uruchomienie za 5 minut")

        sys.stdout.flush()

        time.sleep(300)



def run_v7_enterprise_maintenance():
    try:
        from auto_retraining_runtime import AutoRetrainingRuntime
        result = AutoRetrainingRuntime(min_hours_between_runs=12).run_if_due()
        print(f"[SCHEDULER] V7 ENTERPRISE MAINTENANCE: {result.get('status')}")
        sys.stdout.flush()
    except Exception as e:
        print(f"[SCHEDULER] V7 MAINTENANCE WARNING: {e}")
        sys.stdout.flush()


def main():
    print("🚀 BETBOT PRODUCTION SCHEDULER")
    print(f"⏰ {datetime.now()}")

    sys.stdout.flush()

    run_prematch()


if __name__ == "__main__":
    main()
