
import requests
from datetime import datetime

API_KEY = "5fa34697895a8e2dc8a46e91bcd6dc81"

HEADERS = {
    "x-apisports-key": API_KEY
}


def normalize_fixture(fixture):

    try:

        home = fixture.get("teams", {}).get("home", {}).get("name", "")
        away = fixture.get("teams", {}).get("away", {}).get("name", "")

        league = fixture.get("league", {}).get("name", "")

        minute = fixture.get("fixture", {}).get(
            "status",
            {}
        ).get("elapsed", 0)

        status = fixture.get("fixture", {}).get(
            "status",
            {}
        ).get("short", "NS")

        goals_home = fixture.get("goals", {}).get("home", 0)
        goals_away = fixture.get("goals", {}).get("away", 0)

        score = f"{goals_home}-{goals_away}"

        odds = 1.80

        return {
            "home": home,
            "away": away,
            "league": league,
            "minute": minute,
            "status": status,
            "score": score,
            "signal": "UNDER 2.5",
            "market": "UNDER 2.5",
            "confidence": 72,
            "ev": 6.5,
            "odds": odds,
            "pressure": 50,
            "momentum": 50,
            "dangerous_attacks": 0,
            "shots_on_target": 0,
            "possession": 50,
            "xg_live": 0
        }

    except Exception as e:

        print(f"NORMALIZE ERROR: {e}")

        return None


def api_request(url):

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        print("STATUS:", response.status_code)

        data = response.json()

        fixtures = data.get("response", [])

        print(f"RAW FIXTURES: {len(fixtures)}")

        return fixtures

    except Exception as e:

        print(f"API REQUEST ERROR: {e}")

        return []


def fetch_live_matches():

    print("FETCH MODE -> LIVE")

    url = "https://v3.football.api-sports.io/fixtures?live=all"

    fixtures = api_request(url)

    matches = []

    for fixture in fixtures:

        normalized = normalize_fixture(fixture)

        if normalized:
            matches.append(normalized)

    print(f"NORMALIZED MATCHES: {len(matches)}")

    return matches


def fetch_today_matches():

    print("FETCH MODE -> TODAY")

    today = datetime.utcnow().strftime("%Y-%m-%d")

    url = f"https://v3.football.api-sports.io/fixtures?date={today}"

    fixtures = api_request(url)

    matches = []

    for fixture in fixtures[:50]:

        normalized = normalize_fixture(fixture)

        if normalized:
            matches.append(normalized)

    print(f"TODAY MATCHES: {len(matches)}")

    return matches


def fetch_next_matches():

    print("FETCH MODE -> NEXT")

    url = "https://v3.football.api-sports.io/fixtures?next=20"

    fixtures = api_request(url)

    matches = []

    for fixture in fixtures:

        normalized = normalize_fixture(fixture)

        if normalized:
            matches.append(normalized)

    print(f"NEXT MATCHES: {len(matches)}")

    return matches


# =========================
# MAIN HYBRID FETCH
# =========================

def get_matches():

    # LIVE
    matches = fetch_live_matches()

    if matches:
        return matches

    print("NO LIVE MATCHES -> TRY TODAY")

    # TODAY
    matches = fetch_today_matches()

    if matches:
        return matches

    print("NO TODAY MATCHES -> TRY NEXT")

    # NEXT
    matches = fetch_next_matches()

    return matches


def get_odds_market_data():
    return []


if __name__ == "__main__":

    data = get_matches()

    print(f"FINAL MATCHES: {len(data)}")
    print(data[:3])
