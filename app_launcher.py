import os
import subprocess
import time

print("🚀 APP LAUNCHER START")

port = os.environ.get("PORT", "8080")

# =========================
# START SCHEDULER
# =========================

scheduler_process = subprocess.Popen(
    ["python", "scheduler_engine.py"]
)

print("✅ scheduler_engine.py uruchomiony")

# =========================
# START DASHBOARD
# =========================

dashboard_process = subprocess.Popen(
    [
        "streamlit",
        "run",
        "dashboard_streamlit.py",
        "--server.port",
        port,
        "--server.address",
        "0.0.0.0",
    ]
)

print("✅ dashboard_streamlit.py uruchomiony")

# =========================
# KEEP APP ALIVE
# =========================

while True:
    scheduler_status = scheduler_process.poll()
    dashboard_status = dashboard_process.poll()

    if scheduler_status is not None:
        print("❌ scheduler_engine.py zakończył działanie")

    if dashboard_status is not None:
        print("❌ dashboard_streamlit.py zakończył działanie")

    time.sleep(30)
