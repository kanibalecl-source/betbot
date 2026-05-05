import requests
import time

API_KEY = "5fa34697895a8e2dc8a46e91bcd6dc81"
BASE_URL = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": API_KEY
}

CACHE = {}

def safe_request(url, params):
    for _ in range(3):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=15)
            return r.json()
        except:
            time.sleep(1)
    return None


def get_last_matches(team_id, league_id):
    key = f"{team_id}_{league_id}"
    if key in CACHE:
        return CACHE[key]

    data = safe_request(
        f"{BASE_URL}/fixtures",
        {
            "team": team_id,
            "league": league_id,
            "last": 10
        }
    )

    if not data:
        return []

    matches = data.get("response", [])
    CACHE[key] = matches
    return matches


def calculate_team_strength(team_id, league_id):
    matches = get_last_matches(team_id, league_id)

    if not matches:
        return 1.2, 1.2

    goals_for = 0
    goals_against = 0
    games = 0

    for m in matches:
        try:
            h_id = m["teams"]["home"]["id"]
            a_id = m["teams"]["away"]["id"]
            h = m["goals"]["home"]
            a = m["goals"]["away"]

            if h is None or a is None:
                continue

            if team_id == h_id:
                goals_for += h
                goals_against += a
            else:
                goals_for += a
                goals_against += h

            games += 1
        except:
            continue

    if games == 0:
        return 1.2, 1.2

    attack = goals_for / games
    defense = goals_against / games

    return attack, defense


def get_match_xg(match):
    home_id = match.get("home_id")
    away_id = match.get("away_id")
    league_id = match.get("league_id")

    if not home_id or not away_id or not league_id:
        return None, None

    h_att, h_def = calculate_team_strength(home_id, league_id)
    a_att, a_def = calculate_team_strength(away_id, league_id)

    league_avg = 1.35

    # NORMALIZACJA
    h_att_n = h_att / league_avg
    h_def_n = h_def / league_avg
    a_att_n = a_att / league_avg
    a_def_n = a_def / league_avg

    home_xg = league_avg * h_att_n * a_def_n * 1.08
    away_xg = league_avg * a_att_n * h_def_n

    home_xg = round(min(max(home_xg, 0.3), 4.2), 2)
    away_xg = round(min(max(away_xg, 0.3), 4.2), 2)

    return home_xg, away_xg