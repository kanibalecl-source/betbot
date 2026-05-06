import os
import subprocess
import time

print("NOWA WERSJA START")

port = os.environ.get("PORT", "8080")

print(f"PORT: {port}")

# 🤖 LIVE ENGINE
subprocess.Popen(
    ["python", "live_engine.py"]
)

print("LIVE ENGINE STARTED")

# 📊 STREAMLIT
process = subprocess.Popen(
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

print("STREAMLIT STARTED")

# UTRZYMANIE PROCESU
process.wait()
