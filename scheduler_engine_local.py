import os
import subprocess
import sys
import time
import traceback
from datetime import datetime

from local_env import load_local_env


load_local_env()
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

print("LOCAL SCHEDULER FILE STARTED")
sys.stdout.flush()

BOT_MODES = [
    ("main", "PREMATCH", False),
    ("low", "PREMATCH LOW", True),
    ("risk", "PREMATCH RISK", True),
]

AI_MODES = [
    ("main", "AI"),
    ("low", "AI LOW"),
    ("risk", "AI RISK"),
]


def run_bot_mode(mode: str, label: str, include_all_leagues: bool = False) -> int:
    env = os.environ.copy()
    if include_all_leagues:
        env["KANIBAL_INCLUDE_ALL_LEAGUES"] = "1"
    else:
        env.pop("KANIBAL_INCLUDE_ALL_LEAGUES", None)

    print(f"START LOCAL {label} BOT")
    sys.stdout.flush()
    process = subprocess.Popen(
        [sys.executable, "bot.py", "--mode", mode],
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
    print(f"{label} EXECUTED | CODE={return_code}")
    sys.stdout.flush()
    return int(return_code or 0)


def run_prematch():
    while True:
        try:
            print(f"{datetime.now()}")
            print("FETCHING MATCHES: main + low + risk")
            sys.stdout.flush()

            for mode, label, include_all in BOT_MODES:
                run_bot_mode(mode, label, include_all_leagues=include_all)

            try:
                from live_pipeline_runtime import run_once as run_live_pipeline_once
                live_count = run_live_pipeline_once()
                print(f"LIVE SCHEDULER PIPELINE OK | active={live_count}")
            except Exception as live_error:
                print(f"LIVE SCHEDULER PIPELINE ERROR: {live_error}")

            try:
                from ai_self_learning_runtime import run_self_learning_cycle
                for ai_mode, ai_label in AI_MODES:
                    ai_result = run_self_learning_cycle(mode=ai_mode)
                    print(
                        f"{ai_label} SELF-LEARNING LOOP OK | "
                        f"picks={ai_result.get('ai_picks')} | "
                        f"mode={ai_result.get('mode')} | "
                        f"settled={ai_result.get('settled_samples')}"
                    )
            except Exception as ai_error:
                print(f"AI SELF-LEARNING LOOP ERROR: {ai_error}")

            try:
                from auto_retraining_runtime import AutoRetrainingRuntime
                retrain_result = AutoRetrainingRuntime().run_if_due()
                print(f"AI RETRAINING CHECK | status={retrain_result.get('status')}")
            except Exception as retrain_error:
                print(f"AI RETRAINING CHECK ERROR: {retrain_error}")

            try:
                from persistence_runtime import run_once as persistence_run_once
                persistence_result = persistence_run_once()
                print(f"PERSISTENCE/HISTORY OK | {persistence_result}")
            except Exception as persistence_error:
                print(f"PERSISTENCE/HISTORY ERROR: {persistence_error}")

            print("LOCAL SCHEDULER LOOP OK")
            sys.stdout.flush()
        except Exception as exc:
            print(f"LOCAL PREMATCH ERROR: {exc}")
            traceback.print_exc()
            sys.stdout.flush()

        print("Kolejne lokalne uruchomienie za 5 minut")
        sys.stdout.flush()
        time.sleep(300)


def main():
    print("BETBOT LOCAL PRODUCTION SCHEDULER")
    print(f"{datetime.now()}")
    sys.stdout.flush()
    run_prematch()


if __name__ == "__main__":
    main()
