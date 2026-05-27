import json
import os
from datetime import datetime

def log_shadow_event(payload):
    try:
        os.makedirs("/data", exist_ok=True)

        payload["logged_at"] = datetime.utcnow().isoformat()

        with open("/data/shadow_upgrade_events.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

        print(f"🧠 SHADOW LOGGER SAVED: {payload.get('fixture', 'unknown')}")

    except Exception as e:
        print(f"❌ SHADOW LOGGER ERROR: {e}")
