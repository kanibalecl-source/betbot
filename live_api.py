import requests
from config import API_FOOTBALL_KEY, ODDS_API_KEY

# =========================
# LIVE MATCHES (minuta, wynik)
# =========================
def get_live_matches():
    url = "https://v3.football.api-sports.io/fixtures?live=all"

    headers = {
        "x-apisports-key": API_FOOTBALL_KEY
    }

    res = requests.get(url, headers=headers)
    data = res.json()

    matches = []

    for m in data.get("response", []):

        matches.append({
            "fixture_id": m["fixture"]["id"],
            "mecz": f"{m['teams']['home']['name']} vs {m['teams']['away']['name']}",
            "minute": m["fixture"]["status"]["elapsed"],
            "home_goals": m["goals"]["home"],
            "away_goals": m["goals"]["away"]
        })

    return matches


# =========================
# LIVE ODDS
# =========================
def get_live_odds():
    url = f"https://api.the-odds-api.com/v4/sports/soccer_epl/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=totals"

    res = requests.get(url)
    data = res.json()

    odds_map = {}

    for game in data:
        match = f"{game['home_team']} vs {game['away_team']}"

        try:
            markets = game["bookmakers"][0]["markets"]
            for m in markets:
                if m["key"] == "totals":
                    for outcome in m["outcomes"]:
                        if outcome["name"] == "Over" and outcome["point"] == 2.5:
                            odds_map[match] = outcome["price"]
        except:
            continue

    return odds_map