print("NOWA WERSJA START")

import subprocess
import time
import socket

def wait_for_port(host: str, port: int, timeout: int = 30) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(1)
    return False


# 🤖 BOT
subprocess.Popen(
    ["python", "live_engine.py"]
)


# 📊 DASHBOARD (1)
subprocess.Popen(
    [
        "python",
        "-m",
        "streamlit",
        "run",
        "dashboard_live.py",
        "--server.port",
        "8501",
        "--server.address",
        "0.0.0.0",
    ]
)


# ⏳ sprawdzenie czy działa
ready = wait_for_port("127.0.0.1", 8501, timeout=40)

if ready:
    print("Dashboard działa")
