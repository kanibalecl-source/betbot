import os
import subprocess
import time

print("🚀 BETBOT PRODUCTION START")

port = os.environ.get("PORT", "8080")

# =========================
# BOT CORE
# =========================

subprocess.Popen(
    ["python", "bot.py"]
)

print("✅ bot.py uruchomiony")

# =========================
# DASHBOARD
# =========================

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

print("✅ dashboard uruchomiony")

# =========================
# KEEP ALIVE
# =========================

while True:
    time.sleep(60)
