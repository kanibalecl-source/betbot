import os
import subprocess
import time

print("NOWA WERSJA START")

port = os.environ.get("PORT", "8080")

print(f"PORT: {port}")

process = subprocess.Popen(
    [
        "streamlit",
        "run",
        "dashboard_streamlit.py",
        "--server.port",
        port,
        "--server.address",
        "0.0.0.0",
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
)

print("STREAMLIT STARTED")

while True:
    if process.poll() is not None:
        print("STREAMLIT CRASHED")
        break

    time.sleep(5)
