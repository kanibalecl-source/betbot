import os
import requests
from datetime import datetime, timedelta

API_KEY = os.getenv("API_FOOTBALL_KEY", "5fa34697895a8e2dc8a46e91bcd6dc81")

BASE_URL = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": API_KEY
}

MAX_MATCHES = 100

TOP_LEAGUE_IDS = [
    39, 140, 135, 78, 61, 88, 94, 203, 106,
    2, 3, 71, 128, 235, 218, 119, 103, 113
]


def _request(endpoint, params):
    url = f"{BASE_URL}/{endpoint}"

    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=25
    )

    print(f"STATUS: {response.status_code}")
    print(f"URL PARAMS: {params}")

    try:
        data = response.json()
    except Exception:
        print(f"RAW RESPONSE: {response.text[:500]}")
        return []

    if data.get("errors"):
        print(f"API ERRORS: {data.get('errors')}")

    fixtures = data.get("response", [])

    print(f"RAW FIXTURES: {len(fixtures)}")

    return fixtures


def is_real_match(f):
    try:
        league_name = f["league"]["name"].lower()
        home = f["teams"]["home"]["name"].lower()
        away = f["teams"]["away"]["name"].lower()
    except Exception:
        return False

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


def _normalize_match(f):
    league_id = f["league"]["id"]

    return {
        "match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}",
        "home": f["teams"]["home"]["name"],
        "away": f["teams"]["away"]["name"],
        "home_team": f["teams"]["home"]["name"],
        "away_team": f["teams"]["away"]["name"],
        "league": f["league"]["name"],
        "country": f["league"].get("country", ""),
        "fixture_id": f["fixture"]["id"],
        "home_id": f["teams"]["home"]["id"],
        "away_id": f["teams"]["away"]["id"],
        "league_id": league_id,
        "match_date": f["fixture"].get("date", ""),
        "date": f["fixture"].get("date", ""),
        "minute": f.get("fixture", {}).get("status", {}).get("elapsed") or "",
        "status": f.get("fixture", {}).get("status", {}).get("short") or "NS",
        "score": f"{f.get('goals', {}).get('home', '')}-{f.get('goals', {}).get('away', '')}",
    }


def _filter_and_normalize(fixtures):
    matches = []

    for f in fixtures:
        if len(matches) >= MAX_MATCHES:
            break

        try:
            league_id = f["league"]["id"]
        except Exception:
            continue

        if league_id not in TOP_LEAGUE_IDS:
            continue

        if not is_real_match(f):
            continue

        matches.append(_normalize_match(f))

    return matches


def get_matches():
    """
    Przywrócony stary fetcher + bezpieczne fallbacki dat.

    Najważniejsza poprawka:
    - NIE używamy wymuszonego UTC+2 jako jedynej daty.
    - Railway działa w UTC, a poprzednia wersja działała na dacie UTC.
    - Teraz próbujemy kilka dat, ale zaczynamy od UTC, żeby nie pytać API o zły dzień po północy CEST.
    """

    if not API_KEY or API_KEY == "YOUR_API_KEY":
        print("⚠️ BRAK API_FOOTBALL_KEY — ustaw zmienną Railway albo wpisz klucz w data_api.py")
        return []

    date_candidates = []

    utc_today = datetime.utcnow().strftime("%Y-%m-%d")
    server_today = datetime.now().strftime("%Y-%m-%d")
    cest_today = (datetime.utcnow() + timedelta(hours=2)).strftime("%Y-%m-%d")
    utc_yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    utc_tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    for d in [utc_today, server_today, cest_today, utc_yesterday, utc_tomorrow]:
        if d not in date_candidates:
            date_candidates.append(d)

    for day in date_candidates:
        print(f"FETCH DATE TRY: {day}")

        fixtures = _request(
            "fixtures",
            {"date": day}
        )

        print(f"📅 DATE {day} -> {len(fixtures)}")

        matches = _filter_and_normalize(fixtures)

        print(f"✅ FILTERED MATCHES: {len(matches)}")
        print("🔎 SAMPLE:", matches[:3])

        if matches:
            return matches

    print("NO DATE MATCHES -> TRY NEXT=100")

    fixtures = _request(
        "fixtures",
        {"next": 100}
    )

    matches = _filter_and_normalize(fixtures)

    print(f"✅ NEXT FILTERED MATCHES: {len(matches)}")
    print("🔎 SAMPLE:", matches[:3])

    return matches


def get_odds_market_data(match):
    fixture_id = match.get("fixture_id")

    if not fixture_id:
        return None

    url = f"{BASE_URL}/odds"
    params = {"fixture": fixture_id}

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=25
        )

        print(f"ODDS STATUS: {response.status_code} | fixture={fixture_id}")

        data = response.json()

        if data.get("errors"):
            print(f"ODDS API ERRORS: {data.get('errors')}")

        response_data = data.get("response")

        if not response_data:
            return None

        bookmakers = response_data[0].get("bookmakers", [])
        markets = {}

        for bookmaker in bookmakers:
            bookmaker_name = bookmaker.get("name", "")

            for bet in bookmaker.get("bets", []):
                market_name = bet.get("name")

                for value in bet.get("values", []):
                    try:
                        odd = float(value.get("odd", 0))
                    except Exception:
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

                    elif market_name and "Over/Under" in market_name:
                        try:
                            line = outcome.split(" ")[-1]
                        except Exception:
                            line = ""

                        if "Over" in outcome:
                            key = f"OVER_{line}"
                        elif "Under" in outcome:
                            key = f"UNDER_{line}"

                    if key:
                        if key not in markets:
                            markets[key] = {
                                "best_odds": odd,
                                "bookmaker": bookmaker_name
                            }
                        else:
                            if odd > markets[key]["best_odds"]:
                                markets[key] = {
                                    "best_odds": odd,
                                    "bookmaker": bookmaker_name
                                }

        return markets

    except Exception as e:
        print("❌ ODDS ERROR:", e)
        return None


if __name__ == "__main__":
    matches = get_matches()
    print(f"FINAL MATCHES: {len(matches)}")
    print(matches[:3])
