import os
import subprocess
import time

print("🚀 BETBOT FULL SYSTEM START")

port = os.environ.get("PORT", "8080")

subprocess.Popen(
    ["python", "scheduler_engine.py"]
)

print("✅ scheduler_engine.py uruchomiony")

subprocess.Popen(
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

while True:
    time.sleep(60)
