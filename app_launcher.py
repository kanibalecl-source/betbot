import os
import subprocess
import time

print("NOWA WERSJA START")

port = os.environ.get("PORT", "8080")

print(f"PORT: {port}")

subprocess.run(
    [
        "streamlit",
        "run",
        "dashboard_live.py",
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
