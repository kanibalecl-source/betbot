import os
import signal
import subprocess
import sys
import threading
import time

from server_start_guard import run_server_start_guard_once

print("🚀 APP LAUNCHER START")
sys.stdout.flush()

run_server_start_guard_once()

PORT = os.environ.get("PORT", "8080")
PYTHON = sys.executable or "python3"

PROCESS_SPECS = {
    "scheduler": [PYTHON, "scheduler_engine.py"],
    "live_pipeline": [PYTHON, "live_pipeline_runtime.py"],
    "settlement": [PYTHON, "settle_loop.py"],
    "persistence": [PYTHON, "persistence_runtime.py"],
    "retraining": [PYTHON, "auto_retraining_loop.py"],
    "quality_governance_v8": [PYTHON, "quality_governance_v8_loop.py"],
    "dashboard": [
        PYTHON, "-m", "streamlit", "run", "dashboard_streamlit.py",
        "--server.port", str(PORT),
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
    ],
}

processes = {}


def stream_output(process, prefix):
    try:
        for line in iter(process.stdout.readline, ""):
            if line:
                print(f"{prefix} {line.strip()}")
                sys.stdout.flush()
    except Exception as exc:
        print(f"{prefix} OUTPUT STREAM ERROR: {exc}")
        sys.stdout.flush()


def start_process(name, command):
    print(f"🚀 START {name}: {' '.join(command)}")
    sys.stdout.flush()

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    threading.Thread(
        target=stream_output,
        args=(process, f"[{name.upper()}]"),
        daemon=True,
    ).start()

    print(f"✅ {name} STARTED")
    sys.stdout.flush()
    return process


def start_all():
    for name, command in PROCESS_SPECS.items():
        processes[name] = start_process(name, command)


def shutdown(*args):
    print("🛑 SHUTDOWN START")
    sys.stdout.flush()

    for name, process in list(processes.items()):
        try:
            print(f"🛑 TERMINATE {name}")
            process.terminate()
        except Exception:
            pass

    print("✅ SHUTDOWN COMPLETE")
    sys.stdout.flush()
    sys.exit(0)


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

start_all()

while True:
    try:
        states = {}

        for name, command in PROCESS_SPECS.items():
            process = processes.get(name)
            alive = process is not None and process.poll() is None
            states[name] = alive

            if not alive:
                print(f"❌ {name} CRASHED -> RESTART")
                sys.stdout.flush()
                processes[name] = start_process(name, command)

        state_text = " | ".join(f"{name}={alive}" for name, alive in states.items())
        print(f"💓 HEARTBEAT | {state_text}")
        sys.stdout.flush()

        time.sleep(30)

    except Exception as exc:
        print(f"❌ APP LAUNCHER ERROR: {exc}")
        sys.stdout.flush()
        time.sleep(15)
