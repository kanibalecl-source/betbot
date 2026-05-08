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


def get_fixture_statistics(fixture_id):

    url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={fixture_id}"

    try:

        res = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        data = res.json().get("response", [])

        if len(data) < 2:
            return {}

        home_stats = data[0]["statistics"]
        away_stats = data[1]["statistics"]

        stats = {}

        for stat in home_stats:
            stats[f"home_{stat['type']}"] = stat["value"]

        for stat in away_stats:
            stats[f"away_{stat['type']}"] = stat["value"]

        return stats

    except:
        return {}


def pressure_score(stats):

    try:

        home_shots = int(stats.get("home_Shots on Goal") or 0)
        away_shots = int(stats.get("away_Shots on Goal") or 0)

        home_corners = int(stats.get("home_Corner Kicks") or 0)
        away_corners = int(stats.get("away_Corner Kicks") or 0)

        total_pressure = (
            home_shots +
            away_shots +
            home_corners +
            away_corners
        )

        return total_pressure

    except:
        return 0


def momentum_score(stats):

    try:

        home_attacks = int(stats.get("home_Dangerous Attacks") or 0)
        away_attacks = int(stats.get("away_Dangerous Attacks") or 0)

        home_possession = stats.get("home_Ball Possession") or "0%"
        away_possession = stats.get("away_Ball Possession") or "0%"

        home_possession = int(str(home_possession).replace("%", ""))
        away_possession = int(str(away_possession).replace("%", ""))

        momentum = (
            home_attacks +
            away_attacks +
            home_possession +
            away_possession
        )

        return momentum

    except:
        return 0


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

            fixture_id = m["fixture"]["id"]

            minute = m["fixture"]["status"]["elapsed"] or 0

            home_goals = m["goals"]["home"] or 0
            away_goals = m["goals"]["away"] or 0

            total_goals = home_goals + away_goals

            stats = get_fixture_statistics(fixture_id)

            pressure = pressure_score(stats)

            momentum = momentum_score(stats)

            # =========================
            # LIVE MOMENTUM AI SIGNALS
            # =========================

            live_pick = "NO SIGNAL"
            confidence = 0

            if (
                minute >= 70 and
                pressure >= 10 and
                momentum >= 120
            ):

                live_pick = "OVER 2.5"
                confidence = 90

            elif (
                minute >= 60 and
                pressure >= 8 and
                momentum >= 100
            ):

                live_pick = "BTTS"
                confidence = 84

            elif (
                minute >= 35 and
                total_goals == 0 and
                pressure >= 6 and
                momentum >= 90
            ):

                live_pick = "OVER 1.5"
                confidence = 76

            matches.append({

                "home": m["teams"]["home"]["name"],
                "away": m["teams"]["away"]["name"],
                "league": m["league"]["name"],
                "minute": minute,
                "score": f"{home_goals}:{away_goals}",
                "pressure": pressure,
                "momentum": momentum,
                "signal": live_pick,
                "confidence": confidence,
                "status": m["fixture"]["status"]["short"]

            })

        return matches

    except Exception as e:

        print(f"❌ LIVE API ERROR: {e}")

        return []


print("🚀 LIVE MOMENTUM ENGINE STARTED")

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
