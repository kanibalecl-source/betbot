import math
import os
import requests
import time

API_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()
BASE_URL = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": API_KEY
}

CACHE = {}
MIN_COMPLETED_MATCHES = 5
FINISHED_STATUSES = {"FT", "AET", "PEN"}

def safe_request(url, params):
    if not API_KEY:
        return None
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
        return None

    goals_for = 0
    goals_against = 0
    games = 0

    for m in matches:
        try:
            status = str(m.get("fixture", {}).get("status", {}).get("short") or "").upper()
            if status not in FINISHED_STATUSES:
                continue
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

    if games < MIN_COMPLETED_MATCHES:
        return None

    attack = goals_for / games
    defense = goals_against / games

    return attack, defense, games


def get_match_xg(match):
    home_id = match.get("home_id")
    away_id = match.get("away_id")
    league_id = match.get("league_id")

    if not home_id or not away_id or not league_id:
        return None, None

    home_stats = calculate_team_strength(home_id, league_id)
    away_stats = calculate_team_strength(away_id, league_id)
    if home_stats is None or away_stats is None:
        return None, None
    h_att, h_def, h_games = home_stats
    a_att, a_def, a_games = away_stats
    if h_games <= 0 or a_games <= 0:
        return None, None

    # Wyłącznie średnie z rzeczywistych zakończonych meczów; bez stałej ligowej
    # i bez domyślnej przewagi gospodarza.
    home_xg = (h_att + a_def) / 2
    away_xg = (a_att + h_def) / 2

    if not math.isfinite(home_xg) or not math.isfinite(away_xg):
        return None, None
    if home_xg < 0 or away_xg < 0:
        return None, None

    return round(home_xg, 4), round(away_xg, 4)
