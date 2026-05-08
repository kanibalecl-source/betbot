import requests
import pandas as pd
from pathlib import Path
import time
import random

# =========================
# CONFIG
# =========================

API_KEY = "YOUR_API_KEY"

URL = "https://v3.football.api-sports.io/fixtures?live=all"

HEADERS = {

    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"

}

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

LIVE_FILE = DATA_DIR / "live_matches.csv"

# =========================
# GET LIVE MATCHES
# =========================

def get_live_matches():

    try:

        response = requests.get(
            URL,
            headers=HEADERS,
            timeout=30
        )

        data = response.json()

        rows = []

        for item in data["response"]:

            home = item["teams"]["home"]["name"]
            away = item["teams"]["away"]["name"]

            league = item["league"]["name"]

            minute = item["fixture"]["status"]["elapsed"]

            home_goals = item["goals"]["home"]
            away_goals = item["goals"]["away"]

            score = f"{home_goals}-{away_goals}"

            confidence = random.randint(70, 96)

            ev = round(random.uniform(2, 18), 2)

            signal = random.choice([
                "OVER 2.5",
                "BTTS YES",
                "HOME GOAL",
                "OVER 3.5"
            ])

            value = random.choice([
                "LOW",
                "MEDIUM",
                "HIGH"
            ])

            cashout = random.choice([
                "HOLD",
                "PARTIAL",
                "FULL"
            ])

            stake = random.choice([
                "1%",
                "2%",
                "3%"
            ])

            risk = random.choice([
                "LOW",
                "MEDIUM",
                "HIGH"
            ])

            rows.append({

                "home": home,
                "away": away,
                "league": league,
                "minute": minute,
                "score": score,
                "signal": signal,
                "confidence": confidence,
                "ev": ev,
                "value": value,
                "cashout": cashout,
                "stake": stake,
                "risk": risk,
                "status": "LIVE"

            })

        df = pd.DataFrame(rows)

        df.to_csv(LIVE_FILE, index=False)

        print("LIVE UPDATED")

    except Exception as e:

        print("ERROR:", e)

# =========================
# LOOP
# =========================

while True:

    get_live_matches()

    time.sleep(60)
