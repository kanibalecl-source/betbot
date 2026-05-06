import json
import time

print("LIVE ENGINE START 🚀")

# TESTOWE DANE LIVE
test_data = {
    "status": "online",
    "matches": [
        {
            "home": "Barcelona",
            "away": "Real Madrid",
            "minute": 67,
            "prediction": "OVER 2.5",
            "confidence": 82
        },
        {
            "home": "Manchester City",
            "away": "Liverpool",
            "minute": 54,
            "prediction": "BTTS",
            "confidence": 76
        }
    ]
}

# ZAPIS JSON
with open("live_data.json", "w", encoding="utf-8") as f:
    json.dump(test_data, f, ensure_ascii=False, indent=2)

print("LIVE DATA ZAPISANE ✅")

# UTRZYMANIE PROCESU
while True:
    time.sleep(60)
