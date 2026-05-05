import requests
from datetime import datetime

API_KEY = "5fa34697895a8e2dc8a46e91bcd6dc81"

BASE_URL = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": API_KEY
}

MAX_MATCHES = 100

TOP_LEAGUE_IDS = [
    39, 140, 135, 78, 61, 88, 94, 203, 106,
    2, 3, 71, 128, 235, 218, 119, 103, 113
]


def is_real_match(f):
    league_name = f["league"]["name"].lower()
    home = f["teams"]["home"]["name"].lower()
    away = f["teams"]["away"]["name"].lower()

    bad_words = [
        "women", "u19", "u20", "u21", "youth",
        "reserve", "ii", "iii"
    ]

    if any(b in league_name for b in bad_words):
        return False
    if any(b in home for b in bad_words):
        return False
    if any(b in away for b in bad_words):
        return False

    return True


def get_matches():
    matches = []

    today = datetime.now().strftime("%Y-%m-%d")

    url = f"{BASE_URL}/fixtures"
    params = {"date": today}

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=20)
        data = response.json()

        fixtures = data.get("response", [])
        print(f"📅 TODAY -> {len(fixtures)}")

        for f in fixtures:

            if len(matches) >= MAX_MATCHES:
                break

            league_id = f["league"]["id"]

            if league_id not in TOP_LEAGUE_IDS:
                continue

            if not is_real_match(f):
                continue

            match = {
                "match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}",
                "league": f["league"]["name"],
                "country": f["league"]["country"],
                "fixture_id": f["fixture"]["id"],
                "home_id": f["teams"]["home"]["id"],
                "away_id": f["teams"]["away"]["id"],
                "league_id": league_id
            }

            matches.append(match)

    except Exception as e:
        print("❌ ERROR:", e)

    print(f"✅ MECZE: {len(matches)}")
    print("🔎 SAMPLE:", matches[:3])

    return matches


def get_odds_market_data(match):
    fixture_id = match.get("fixture_id")

    if not fixture_id:
        return None

    url = f"{BASE_URL}/odds"
    params = {"fixture": fixture_id}

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=20)
        data = response.json()

        response_data = data.get("response")
        if not response_data:
            return None

        bookmakers = response_data[0].get("bookmakers", [])
        markets = {}

        for bookmaker in bookmakers:
            for bet in bookmaker.get("bets", []):
                market_name = bet.get("name")

                for value in bet.get("values", []):
                    try:
                        odd = float(value.get("odd", 0))
                    except:
                        continue

                    outcome = value.get("value")
                    key = None

                    if market_name == "Match Winner":
                        if outcome == "Home":
                            key = "HOME_WIN"
                        elif outcome == "Draw":
                            key = "DRAW"
                        elif outcome == "Away":
                            key = "AWAY_WIN"

                    elif market_name == "Both Teams Score":
                        if outcome == "Yes":
                            key = "BTTS_YES"
                        elif outcome == "No":
                            key = "BTTS_NO"

                    elif "Over/Under" in market_name:
                        line = outcome.split(" ")[-1]

                        if "Over" in outcome:
                            key = f"OVER_{line}"
                        elif "Under" in outcome:
                            key = f"UNDER_{line}"

                    if key:
                        if key not in markets:
                            markets[key] = {"best_odds": odd}
                        else:
                            markets[key]["best_odds"] = max(
                                markets[key]["best_odds"], odd
                            )

        return markets

    except Exception as e:
        print("❌ ODDS ERROR:", e)
        return None