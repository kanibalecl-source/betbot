import os

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


# 🔌 PORT z Railway
port = os.environ.get("PORT", "8501")


# 🤖 BOT WYŁĄCZONY
# subprocess.Popen(
#     ["python", "live_engine.py"]
# )

# 📊 DASHBOARD
subprocess.Popen(
    [
        "python",
        "-m",
        "streamlit",
        "run",
        "dashboard_live.py",
        "--server.port",
        port,
        "--server.address",
        "0.0.0.0",
    ]
)


# ⏳ czekamy aż dashboard ruszy
ready = wait_for_port("127.0.0.1", int(port), timeout=40)

if ready:
    print("Dashboard działa 🚀")
else:
    print("Dashboard NIE wystartował ❌")


# 🔁 utrzymanie procesu (Railway tego wymaga)
while True:
    time.sleep(60)
