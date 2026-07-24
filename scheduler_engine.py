import os
import subprocess
import sys
import time
import traceback
from datetime import datetime

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

print("SCHEDULER FILE STARTED")
sys.stdout.flush()

BOT_MODES = [
    ("main", "PREMATCH", False),
]

AI_MODES = [
    ("main", "AI"),
]


def run_bot_mode(mode: str, label: str, include_all_leagues: bool = False) -> int:
    env = os.environ.copy()
    if include_all_leagues:
        env["KANIBAL_INCLUDE_ALL_LEAGUES"] = "1"
    else:
        env.pop("KANIBAL_INCLUDE_ALL_LEAGUES", None)

    print(f"START {label} BOT")
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
            print("FETCHING MATCHES: main")
            sys.stdout.flush()

            for mode, label, include_all in BOT_MODES:
                run_bot_mode(mode, label, include_all_leagues=include_all)

            print("LIVE PIPELINE OWNER | live_pipeline process")

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

            # Retraining has one owner. The legacy runtime is intentionally
            # not called because it bypassed the complete evidence chain.
            print("AI RETRAINING OWNER | autonomous_quality_v11")

            print("PERSISTENCE OWNER | persistence process")

            print("SCHEDULER LOOP OK")
            sys.stdout.flush()
        except Exception as exc:
            print(f"PREMATCH ERROR: {exc}")
            traceback.print_exc()
            sys.stdout.flush()

        print("Kolejne lokalne uruchomienie za 5 minut")
        sys.stdout.flush()
        time.sleep(300)


def main():
    print("BETBOT PRODUCTION SCHEDULER")
    print(f"{datetime.now()}")
    sys.stdout.flush()
    run_prematch()


if __name__ == "__main__":
    main()
