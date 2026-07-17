import time
import requests
import pandas as pd
from pathlib import Path

from config import API_FOOTBALL_KEY
from storage_paths import DATA_DIR

HEADERS = {
    "x-apisports-key": API_FOOTBALL_KEY
}

DATA_DIR.mkdir(exist_ok=True)

LIVE_FILE = DATA_DIR / "live_matches.csv"


def get_live_matches():
    url = "https://v3.football.api-sports.io/fixtures?live=all"

    try:
        res = requests.get(url, headers=HEADERS, timeout=20)
        res.raise_for_status()

        data = res.json().get("response", [])

        matches = []

        for m in data:
            matches.append({
                "fixture_id": m["fixture"]["id"],
                "home": m["teams"]["home"]["name"],
                "away": m["teams"]["away"]["name"],
                "league": m["league"]["name"],
                "minute": m["fixture"]["status"]["elapsed"] or 0,
                "score": f"{m['goals']['home']}:{m['goals']['away']}",
                "status": m["fixture"]["status"]["short"]
            })

        return matches

    except Exception as e:
        print(f"❌ LIVE API ERROR: {e}")
        return []


print("🚀 LIVE ENGINE STARTED")

while True:

    print("💓 LIVE LOOP")

    live_matches = get_live_matches()

    print(live_matches[:2])

    if live_matches:

        df = pd.DataFrame(live_matches)

        df.to_csv(LIVE_FILE, index=False)

        print("✅ live_matches.csv UPDATED")

    else:
        print("⚠️ NO LIVE MATCHES")

    time.sleep(60)
