import time
import sys
import traceback

print("🚨🚨🚨 NOWY SCHEDULER DZIAŁA 🚨🚨🚨")

sys.stdout.flush()

while True:
    try:
        print("💓 LOOP DZIAŁA")

        sys.stdout.flush()

        time.sleep(10)

    except Exception as e:
        print(f"❌ SCHEDULER ERROR: {e}")

        traceback.print_exc()

        sys.stdout.flush()

        time.sleep(5)
