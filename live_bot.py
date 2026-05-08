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


def get_live_odds(fixture_id):

    url = f"https://v3.football.api-sports.io/odds/live?fixture={fixture_id}"

    try:

        res = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        data = res.json().get("response", [])

        if not data:
            return None

        bookmakers = data[0].get("bookmakers", [])

        for book in bookmakers:

            bets = book.get("bets", [])

            for bet in bets:

                if bet["name"] == "Goals Over/Under":

                    for value in bet["values"]:

                        if value["value"] == "Over 2.5":

                            return float(value["odd"])

        return None

    except:
        return None


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


def calculate_value(confidence, odds):

    try:

        implied_probability = 1 / odds

        model_probability = confidence / 100

        value = (
            model_probability -
            implied_probability
        ) * 100

        return round(value, 2)

    except:
        return 0


def calculate_ev(confidence, odds):

    try:

        probability = confidence / 100

        ev = (
            probability * odds
        ) - 1

        return round(ev * 100, 2)

    except:
        return 0


def cashout_signal(minute, pressure, momentum, confidence):

    # =========================
    # CASHOUT AI
    # =========================

    if (
        minute >= 80 and
        pressure <= 4 and
        momentum <= 60
    ):

        return "FULL CASHOUT"

    elif (
        minute >= 70 and
        confidence <= 55
    ):

        return "PARTIAL CASHOUT"

    elif (
        pressure >= 12 and
        momentum >= 140
    ):

        return "HOLD POSITION"

    return "NO CASHOUT"


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

            odds = get_live_odds(fixture_id)

            # =========================
            # LIVE SIGNALS
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

            value = calculate_value(confidence, odds) if odds else 0

            ev = calculate_ev(confidence, odds) if odds else 0

            cashout = cashout_signal(
                minute,
                pressure,
                momentum,
                confidence
            )

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
                "odds": odds,
                "value": value,
                "ev": ev,
                "cashout": cashout,
                "status": m["fixture"]["status"]["short"]

            })

        return matches

    except Exception as e:

        print(f"❌ LIVE API ERROR: {e}")

        return []


print("🚀 CASHOUT AI ENGINE STARTED")

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
