import os
import subprocess
import time

print("🚀 APP LAUNCHER START")

port = os.environ.get("PORT", "8080")

try:
    print("🚀 START scheduler_engine.py")

    scheduler_process = subprocess.Popen(
        ["python3", "scheduler_engine.py"]
    )

    print("✅ scheduler_engine.py STARTED")

except Exception as e:
    print(f"❌ scheduler_engine.py ERROR: {e}")

try:
    print("🚀 START dashboard_streamlit.py")

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

    print("✅ dashboard_streamlit.py STARTED")

except Exception as e:
    print(f"❌ dashboard_streamlit.py ERROR: {e}")

print("✅ APP RUNNING")

while True:
    print("💓 HEARTBEAT")

    time.sleep(30)
