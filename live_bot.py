import time
import requests
import pandas as pd
from pathlib import Path

from config import API_FOOTBALL_KEY

HEADERS = {
    "x-apisports-key": API_FOOTBALL_KEY
}

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

LIVE_FILE = DATA_DIR / "live_matches.csv"


def get_live_matches():

    url = "https://v3.football.api-sports.io/fixtures?live=all"

    try:
        res = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        res.raise_for_status()

        data = res.json().get("response", [])

        matches = []

        for m in data:

            minute = m["fixture"]["status"]["elapsed"] or 0

            home_goals = m["goals"]["home"] or 0
            away_goals = m["goals"]["away"] or 0

            total_goals = home_goals + away_goals

            # =========================
            # LIVE AI SIGNALS
            # =========================

            live_pick = "NO SIGNAL"
            confidence = 0

            if minute >= 70 and total_goals <= 2:
                live_pick = "OVER 2.5"
                confidence = 82

            elif minute >= 55 and total_goals >= 1:
                live_pick = "BTTS"
                confidence = 76

            elif minute >= 35 and total_goals == 0:
                live_pick = "OVER 1.5"
                confidence = 68

            matches.append({

                "home": m["teams"]["home"]["name"],
                "away": m["teams"]["away"]["name"],
                "league": m["league"]["name"],
                "minute": minute,
                "score": f"{home_goals}:{away_goals}",
                "signal": live_pick,
                "confidence": confidence,
                "status": m["fixture"]["status"]["short"]

            })

        return matches

    except Exception as e:

        print(f"❌ LIVE API ERROR: {e}")

        return []


print("🚀 LIVE SIGNAL ENGINE STARTED")

while True:

    print("💓 LIVE LOOP")

    live_matches = get_live_matches()

    if live_matches:

        df = pd.DataFrame(live_matches)

        df.to_csv(LIVE_FILE, index=False)

        print(f"✅ LIVE MATCHES UPDATED: {len(df)}")

    else:

        print("⚠️ NO LIVE MATCHES")

    time.sleep(60)
