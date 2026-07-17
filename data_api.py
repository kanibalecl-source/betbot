import os
import requests
from datetime import datetime, timedelta

API_KEY = os.getenv("API_FOOTBALL_KEY", "")

BASE_URL = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": API_KEY
}

MAX_MATCHES = 100

TOP_LEAGUE_IDS = [
    39, 140, 135, 78, 61,
    88, 94, 203, 106,
    2, 3, 71, 128,
    235, 218, 119,
    103, 113
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
        "women",
        "u19",
        "u20",
        "u21",
        "youth",
        "reserve",
        "ii",
        "iii"
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
    skipped = {
        "finished_or_cancelled": 0,
        "league_not_top": 0,
        "not_real_match": 0,
        "bad_payload": 0,
    }

    for f in fixtures:

        if len(matches) >= MAX_MATCHES:
            break

        try:
            league_id = f["league"]["id"]

            status = f.get(
                "fixture",
                {}
            ).get(
                "status",
                {}
            ).get(
                "short",
                ""
            )

        except Exception:
            skipped["bad_payload"] += 1
            continue

        if status in [
            "FT",
            "AET",
            "PEN",
            "CANC",
            "PST"
        ]:
            skipped["finished_or_cancelled"] += 1
            continue

        include_all_leagues = str(os.getenv("KANIBAL_INCLUDE_ALL_LEAGUES", "0")).lower() in {"1", "true", "yes", "on"}
        if not include_all_leagues and league_id not in TOP_LEAGUE_IDS:
            skipped["league_not_top"] += 1
            continue

        if not is_real_match(f):
            skipped["not_real_match"] += 1
            continue

        matches.append(_normalize_match(f))

    print(f"NORMALIZE SKIP STATS: {skipped}")

    return matches


def get_matches():

    if not API_KEY or API_KEY == "YOUR_API_KEY":
        print("BRAK API_FOOTBALL_KEY")
        return []

    date_candidates = []

    utc_today = datetime.utcnow().strftime("%Y-%m-%d")

    server_today = datetime.now().strftime("%Y-%m-%d")

    cest_today = (
        datetime.utcnow() + timedelta(hours=2)
    ).strftime("%Y-%m-%d")

    utc_tomorrow = (
        datetime.utcnow() + timedelta(days=1)
    ).strftime("%Y-%m-%d")

    for d in [
        utc_today,
        server_today,
        cest_today,
        utc_tomorrow
    ]:
        if d not in date_candidates:
            date_candidates.append(d)

    for day in date_candidates:

        print(f"FETCH DATE: {day}")

        fixtures = _request(
            "fixtures",
            {"date": day}
        )

        matches = _filter_and_normalize(fixtures)

        print(f"NORMALIZED MATCHES: {len(matches)}")

        if matches:
            return matches

    print("NO DATE MATCHES -> zachowuje poprzedni auto_all_picks.csv")
    return []


# =========================
# KLUCZOWY FIX
# =========================

def _normalize_total_line(value):
    try:
        text = str(value or "").strip()
        # API-Football usually returns "Over 2.5" / "Under 2.5"
        parts = text.replace(",", ".").split()
        for part in reversed(parts):
            try:
                return f"{float(part):.1f}"
            except Exception:
                continue
    except Exception:
        pass
    return ""


def _normalize_double_chance(value):
    text = str(value or "").strip().lower()
    text = (
        text.replace(" ", "")
        .replace("-", "/")
        .replace("_", "/")
        .replace("or", "/")
    )

    # Common API names:
    # Home/Draw, Draw/Away, Home/Away
    # 1X, X2, 12
    if text in {"home/draw", "1/x", "1x", "homeor draw", "home/draw"}:
        return "DOUBLE_1X"

    if text in {"draw/away", "x/2", "x2", "draw/away"}:
        return "DOUBLE_X2"

    if text in {"home/away", "1/2", "12", "home/away"}:
        return "DOUBLE_12"

    if "home" in text and "draw" in text:
        return "DOUBLE_1X"

    if "draw" in text and "away" in text:
        return "DOUBLE_X2"

    if "home" in text and "away" in text:
        return "DOUBLE_12"

    return None


def _iter_fixture_odds(match):

    fixture_id = match.get("fixture_id")

    if not fixture_id:
        return []

    url = f"{BASE_URL}/odds"
    params = {"fixture": fixture_id}

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
        return []

    rows = []

    for bookmaker in response_data[0].get("bookmakers", []):

        bookmaker_name = str(bookmaker.get("name", "")).strip()

        for bet in bookmaker.get("bets", []):

            market_name = str(bet.get("name") or "").strip()

            for value in bet.get("values", []):

                try:
                    odd = float(value.get("odd", 0))
                except Exception:
                    continue

                if odd <= 1:
                    continue

                outcome = str(value.get("value") or "").strip()
                key = None

                if market_name == "Match Winner":
                    if outcome == "Home":
                        key = "HOME_WIN"
                    elif outcome == "Draw":
                        key = "DRAW"
                    elif outcome == "Away":
                        key = "AWAY_WIN"

                elif market_name == "Double Chance":
                    key = _normalize_double_chance(outcome)

                elif market_name == "Both Teams Score":
                    if outcome == "Yes":
                        key = "BTTS_YES"
                    elif outcome == "No":
                        key = "BTTS_NO"

                elif market_name and "Over/Under" in market_name:
                    line = _normalize_total_line(outcome)
                    if line in {"0.5", "1.5", "2.5", "3.5", "4.5"}:
                        if "Over" in outcome:
                            key = f"OVER_{line}"
                        elif "Under" in outcome:
                            key = f"UNDER_{line}"

                if key:
                    rows.append({"market": key, "odds": odd, "bookmaker": bookmaker_name})

    return rows


def get_odds_market_data(match):

    try:
        rows = _iter_fixture_odds(match)
        markets = {}

        for row in rows:
            key = row["market"]
            item = markets.setdefault(key, {
                "best_odds": None,
                "bookmaker": "",
                "all_odds": [],
                "by_bookmaker": {},
            })
            item["all_odds"].append(row["odds"])
            # Keep the exact outcome price per bookmaker. This allows margin
            # checks only on complete, internally consistent market books.
            item["by_bookmaker"][row["bookmaker"]] = row["odds"]
            if item["best_odds"] is None or row["odds"] > item["best_odds"]:
                item["best_odds"] = row["odds"]
                item["bookmaker"] = row["bookmaker"]

        if markets:
            print(f"ODDS MARKETS: {sorted(list(markets.keys()))}")

        return markets

    except Exception as e:
        print("ODDS ERROR:", e)
        return {}


def get_bookmaker_market_odds(match, market_key, bookmaker_query="superbet"):

    target_market = str(market_key or "").strip().upper()
    wanted = str(bookmaker_query or "").strip().lower()

    if not target_market:
        return None

    try:
        best_fallback = None

        for row in _iter_fixture_odds(match):
            if row["market"] != target_market:
                continue

            if wanted and wanted in str(row["bookmaker"]).lower():
                return row

            if best_fallback is None or row["odds"] > best_fallback["odds"]:
                best_fallback = row

        return best_fallback

    except Exception as e:
        print("BOOKMAKER ODDS ERROR:", e)
        return None

if __name__ == "__main__":

    matches = get_matches()

    print(f"FINAL MATCHES: {len(matches)}")
    print(matches[:3])
