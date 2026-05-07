import time

print("🚀 LIVE BOT STARTED")

while True:
    try:
        print("💓 HEARTBEAT")
        time.sleep(10)

    except Exception as e:
        print("❌ ERROR:", e)
