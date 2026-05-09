import os
import subprocess
import time
import signal
import sys
import threading

print("🚀 APP LAUNCHER START")

PORT = os.environ.get("PORT", "8080")

processes = []


def stream_output(process, prefix):
    for line in iter(process.stdout.readline, ''):
        if line:
            print(f"{prefix} {line.strip()}")


def start_scheduler():
    print("🚀 START scheduler_engine.py")

    process = subprocess.Popen(
        ["python3", "scheduler_engine.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    threading.Thread(
        target=stream_output,
        args=(process, "[SCHEDULER]"),
        daemon=True,
    ).start()

    print("✅ scheduler_engine.py STARTED")

    return process


def start_dashboard():
    print("🚀 START dashboard_streamlit.py")

    process = subprocess.Popen(
        [
            "python3",
            "-m",
            "streamlit",
            "run",
            "dashboard_streamlit.py",
            "--server.port",
            str(PORT),
            "--server.address",
            "0.0.0.0",
            "--server.headless",
            "true",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    threading.Thread(
        target=stream_output,
        args=(process, "[DASHBOARD]"),
        daemon=True,
    ).start()

    print("✅ dashboard_streamlit.py STARTED")

    return process


def shutdown(*args):
    print("🛑 SHUTDOWN START")

    for p in processes:
        try:
            p.terminate()
        except Exception:
            pass

    print("✅ SHUTDOWN COMPLETE")

    sys.exit(0)


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

scheduler_process = start_scheduler()
dashboard_process = start_dashboard()

processes = [scheduler_process, dashboard_process]

while True:
    try:
        scheduler_alive = scheduler_process.poll() is None
        dashboard_alive = dashboard_process.poll() is None

        print(
            f"💓 HEARTBEAT | scheduler={scheduler_alive} | dashboard={dashboard_alive}"
        )

        if not scheduler_alive:
            print("❌ scheduler_engine.py CRASHED -> RESTART")

            scheduler_process = start_scheduler()

            processes[0] = scheduler_process

        if not dashboard_alive:
            print("❌ dashboard_streamlit.py CRASHED -> RESTART")

            dashboard_process = start_dashboard()

            processes[1] = dashboard_process

        time.sleep(30)

    except Exception as e:
        print(f"❌ APP LAUNCHER ERROR: {e}")

        time.sleep(15)
