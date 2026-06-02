import os
import signal
import subprocess
import sys
import threading
import time

from local_env import load_local_env


loaded = load_local_env()

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

print("BETBOT LOCAL APP LAUNCHER START")
print("LOCAL MODE: no server files are touched; all writes stay inside this folder.")
if loaded:
    print("Loaded local variables:", ", ".join(sorted(loaded)))
else:
    print("No .env.local file loaded. Dashboard can start, but API features need keys.")
sys.stdout.flush()

PORT = os.environ.get("LOCAL_PORT") or os.environ.get("PORT") or "8501"
os.environ["PORT"] = str(PORT)
PYTHON = sys.executable or "python"

PROCESS_SPECS = {
    "scheduler": [PYTHON, "scheduler_engine_local.py"],
    "live_pipeline": [PYTHON, "live_pipeline_runtime.py"],
    "settlement": [PYTHON, "settle_loop.py"],
    "persistence": [PYTHON, "persistence_runtime.py"],
    "retraining": [PYTHON, "auto_retraining_loop.py"],
    "dashboard": [
        PYTHON,
        "-m",
        "streamlit",
        "run",
        "dashboard_streamlit.py",
        "--server.port",
        str(PORT),
        "--server.address",
        "127.0.0.1",
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
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
    print(f"LOCAL START {name}: {' '.join(command)}")
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
    print(f"{name} STARTED")
    sys.stdout.flush()
    return process


def start_all():
    for name, command in PROCESS_SPECS.items():
        processes[name] = start_process(name, command)


def shutdown(*args):
    print("LOCAL SHUTDOWN START")
    sys.stdout.flush()
    for name, process in list(processes.items()):
        try:
            print(f"TERMINATE {name}")
            process.terminate()
        except Exception:
            pass
    print("LOCAL SHUTDOWN COMPLETE")
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
                print(f"{name} CRASHED -> LOCAL RESTART")
                sys.stdout.flush()
                processes[name] = start_process(name, command)

        state_text = " | ".join(f"{name}={alive}" for name, alive in states.items())
        print(f"LOCAL HEARTBEAT | {state_text}")
        sys.stdout.flush()
        time.sleep(30)
    except Exception as exc:
        print(f"LOCAL APP LAUNCHER ERROR: {exc}")
        sys.stdout.flush()
        time.sleep(15)

