import pandas as pd
from pathlib import Path
from datetime import datetime
import random
import time

# =========================
# DATA PATH
# =========================

DATA_DIR = Path("data")

DATA_DIR.mkdir(exist_ok=True)

LIVE_FILE = DATA_DIR / "live_matches.csv"

# =========================
# SAMPLE LIVE MATCHES
# =========================

MATCHES = [

    {
        "home": "Barcelona",
        "away": "Real Madrid",
        "league": "La Liga"
    },

    {
        "home": "Liverpool",
        "away": "Arsenal",
        "league": "Premier League"
    },

    {
        "home": "Inter",
        "away": "Milan",
        "league": "Serie A"
    },

    {
        "home": "PSG",
        "away": "Monaco",
        "league": "Ligue 1"
    }

]

# =========================
# GENERATE LIVE DATA
# =========================

def generate_live_data():

    rows = []

    for match in MATCHES:

        minute = random.randint(1, 90)

        home_goals = random.randint(0, 4)
        away_goals = random.randint(0, 4)

        signal = random.choice([
            "OVER 2.5",
            "BTTS YES",
            "OVER 3.5",
            "HOME GOAL",
            "AWAY GOAL"
        ])

        confidence = random.randint(70, 97)

        ev = round(random.uniform(3, 18), 2)

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
            "3%",
            "5%"
        ])

        risk = random.choice([
            "LOW",
            "MEDIUM",
            "HIGH"
        ])

        row = {

            "home": match["home"],
            "away": match["away"],
            "league": match["league"],
            "minute": minute,
            "score": f"{home_goals}-{away_goals}",
            "signal": signal,
            "confidence": confidence,
            "ev": ev,
            "value": value,
            "cashout": cashout,
            "stake": stake,
            "risk": risk,
            "status": "LIVE",
            "updated_at": datetime.utcnow()

        }

        rows.append(row)

    return pd.DataFrame(rows)

# =========================
# LOOP
# =========================

while True:

    df = generate_live_data()

    df.to_csv(LIVE_FILE, index=False)

    print("LIVE UPDATED")

    time.sleep(60)
