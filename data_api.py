
import requests

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
        ).get("short", "LIVE")

        goals_home = fixture.get("goals", {}).get("home", 0)
        goals_away = fixture.get("goals", {}).get("away", 0)

        score = f"{goals_home}-{goals_away}"

        return {
            "home": home,
            "away": away,
            "league": league,
            "minute": minute,
            "status": status,
            "score": score,
            "signal": "LIVE",
            "market": "LIVE",
            "confidence": 55,
            "ev": 5,
            "odds": 1.80,
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


def fetch_live_matches():

    try:

        url = "https://v3.football.api-sports.io/fixtures?live=all"

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        print("STATUS:", response.status_code)

        data = response.json()

        fixtures = data.get("response", [])

        print(f"RAW FIXTURES: {len(fixtures)}")

        matches = []

        for fixture in fixtures:

            normalized = normalize_fixture(fixture)

            if normalized:
                matches.append(normalized)

        print(f"NORMALIZED MATCHES: {len(matches)}")

        return matches

    except Exception as e:

        print(f"FETCH LIVE ERROR: {e}")

        return []


# =========================
# COMPATIBILITY FUNCTIONS
# =========================

def get_matches():
    return fetch_live_matches()


def get_odds_market_data():
    return []


if __name__ == "__main__":

    matches = fetch_live_matches()

    print(matches[:3])
