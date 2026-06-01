import subprocess
import time
import traceback
import sys
import os
from datetime import datetime

print("🚨 SCHEDULER FILE STARTED")

sys.stdout.flush()


BOT_MODES = [
    ("main", "BOT OBECNY"),
    ("low", "MECZE LOW"),
    ("risk", "MECZE RISK"),
]


def run_bot_mode(mode, label):
    print(f"🚀 START {label}")
    print(f"⏰ {datetime.now()}")

    sys.stdout.flush()

    env = os.environ.copy()
    env["KANIBAL_BOT_MODE"] = mode
    env["KANIBAL_INCLUDE_ALL_LEAGUES"] = "1" if mode in {"low", "risk"} else ""

    process = subprocess.Popen(
        ["python3", "bot.py", "--mode", mode],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )

    while True:
        output = process.stdout.readline()

        if output == "" and process.poll() is not None:
            break

        if output:
            print(f"[{label}] {output.strip()}")
            sys.stdout.flush()

    return_code = process.poll()
    print(f"✅ {label} EXECUTED | CODE={return_code}")
    sys.stdout.flush()
    return return_code


def run_prematch():
    while True:
        try:
            print("📡 FETCHING MATCHES")

            sys.stdout.flush()

            for mode, label in BOT_MODES:
                run_bot_mode(mode, label)

            try:
                from live_pipeline_runtime import run_once as run_live_pipeline_once
                live_count = run_live_pipeline_once()
                print(f"✅ LIVE SCHEDULER PIPELINE OK | active={live_count}")
            except Exception as live_error:
                print(f"❌ LIVE SCHEDULER PIPELINE ERROR: {live_error}")

            print("✅ LIVE SAVED")
            try:
                from ai_self_learning_runtime import run_self_learning_cycle
                ai_result = run_self_learning_cycle()
                print(f"✅ AI SELF-LEARNING LOOP OK | picks={ai_result.get('ai_picks')} | mode={ai_result.get('mode')} | settled={ai_result.get('settled_samples')}")
            except Exception as ai_error:
                print(f"❌ AI SELF-LEARNING LOOP ERROR: {ai_error}")

            try:
                from auto_retraining_runtime import AutoRetrainingRuntime
                retrain_result = AutoRetrainingRuntime().run_if_due()
                print(f"✅ AI RETRAINING CHECK | status={retrain_result.get('status')}")
            except Exception as retrain_error:
                print(f"⚠️ AI RETRAINING CHECK ERROR: {retrain_error}")

            try:
                from persistence_runtime import run_once as persistence_run_once
                persistence_result = persistence_run_once()
                print(f"✅ PERSISTENCE/HISTORY OK | {persistence_result}")
            except Exception as persistence_error:
                print(f"⚠️ PERSISTENCE/HISTORY ERROR: {persistence_error}")
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
