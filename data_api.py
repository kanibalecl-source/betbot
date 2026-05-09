import os
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# Najpierw Railway Variables / .env, awaryjnie stary klucz z pliku.
API_KEY = (
    os.getenv("API_FOOTBALL_KEY")
    or os.getenv("APISPORTS_KEY")
    or os.getenv("RAPIDAPI_KEY")
    or "5fa34697895a8e2dc8a46e91bcd6dc81"
)

BASE_URL = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": API_KEY
}

MAX_MATCHES = int(os.getenv("MAX_MATCHES", "100"))
TIMEZONE = os.getenv("BOT_TIMEZONE", "Europe/Warsaw")

TOP_LEAGUE_IDS = [
    39, 140, 135, 78, 61, 88, 94, 203, 106,
    2, 3, 71, 128, 235, 218, 119, 103, 113
]

FINISHED_STATUSES = {
    "FT",
    "AET",
    "PEN",
    "AWD",
    "WO",
    "CANC",
    "ABD",
    "SUSP",
    "INT",
    "PST"
}


def _api_get(endpoint, params):
    url = f"{BASE_URL}{endpoint}"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=25
        )

        print(f"🌐 API GET {endpoint} {params} -> HTTP {response.status_code}")

        try:
            data = response.json()
        except Exception:
            print(f"❌ API JSON ERROR: {response.text[:500]}")
            return {}

        errors = data.get("errors")
        if errors:
            print(f"❌ API ERRORS: {errors}")

        paging = data.get("paging")
        if paging:
            print(f"📄 API PAGING: {paging}")

        return data

    except Exception as e:
        print(f"❌ API REQUEST ERROR: {e}")
        return {}


def is_real_match(f):
    try:
        league_name = f["league"]["name"].lower()
        home = f["teams"]["home"]["name"].lower()
        away = f["teams"]["away"]["name"].lower()
    except Exception:
        return False

    bad_words = [
        "women", "u19", "u20", "u21", "u23", "youth",
        "reserve", "reserves", " ii", " iii"
    ]

    if any(b in league_name for b in bad_words):
        return False
    if any(b in home for b in bad_words):
        return False
    if any(b in away for b in bad_words):
        return False

    return True


def _fixture_to_match(f):
    status_obj = f.get("fixture", {}).get("status", {}) or {}
    goals = f.get("goals", {}) or {}
    fixture = f.get("fixture", {}) or {}
    teams = f.get("teams", {}) or {}
    league = f.get("league", {}) or {}

    home_team = teams.get("home", {}).get("name", "")
    away_team = teams.get("away", {}).get("name", "")

    status_short = status_obj.get("short", "")
    elapsed = status_obj.get("elapsed", "")

    home_goals = goals.get("home")
    away_goals = goals.get("away")

    if home_goals is None or away_goals is None:
        score = ""
    else:
        score = f"{home_goals}-{away_goals}"

    return {
        "match": f"{home_team} vs {away_team}",
        "home": home_team,
        "away": away_team,
        "home_team": home_team,
        "away_team": away_team,
        "league": league.get("name", ""),
        "country": league.get("country", ""),
        "fixture_id": fixture.get("id"),
        "home_id": teams.get("home", {}).get("id"),
        "away_id": teams.get("away", {}).get("id"),
        "league_id": league.get("id"),
        "match_date": fixture.get("date", ""),
        "date": fixture.get("date", ""),
        "status": status_short,
        "minute": elapsed or "",
        "score": score
    }


def _collect_from_fixtures(fixtures, allow_any_league=False):
    matches = []
    skipped_finished = 0
    skipped_league = 0
    skipped_fake = 0

    for f in fixtures:
        if len(matches) >= MAX_MATCHES:
            break

        status_short = str(
            f.get("fixture", {}).get("status", {}).get("short", "")
        ).upper()

        if status_short in FINISHED_STATUSES:
            skipped_finished += 1
            continue

        league_id = f.get("league", {}).get("id")

        if not allow_any_league and league_id not in TOP_LEAGUE_IDS:
            skipped_league += 1
            continue

        if not is_real_match(f):
            skipped_fake += 1
            continue

        matches.append(_fixture_to_match(f))

    print(
        f"🧹 FILTERED -> accepted={len(matches)} "
        f"finished={skipped_finished} league={skipped_league} fake={skipped_fake}"
    )

    return matches


def get_matches():
    """
    Stabilne pobieranie meczów.

    Naprawia przypadek:
    TODAY -> 0
    MECZE -> 0

    Strategia:
    1. próbuje live=all,
    2. próbuje dziś + kolejne dni,
    3. najpierw TOP_LEAGUE_IDS,
    4. jeśli top ligi puste, bierze realne mecze z dowolnych lig,
    5. loguje błędy API zamiast cicho zwracać [].
    """

    all_candidates = []

    # 1) LIVE endpoint
    live_data = _api_get(
        "/fixtures",
        {
            "live": "all",
            "timezone": TIMEZONE
        }
    )

    live_fixtures = live_data.get("response", []) or []
    print(f"🔴 LIVE API -> {len(live_fixtures)}")

    if live_fixtures:
        matches = _collect_from_fixtures(live_fixtures, allow_any_league=False)

        if not matches:
            print("⚠️ LIVE TOP leagues empty -> fallback all real live leagues")
            matches = _collect_from_fixtures(live_fixtures, allow_any_league=True)

        if matches:
            print(f"✅ MECZE LIVE: {len(matches)}")
            print("🔎 SAMPLE:", matches[:3])
            return matches

    # 2) Date fallback: today + next 3 days
    now = datetime.now(ZoneInfo(TIMEZONE))
    dates = [
        (now + timedelta(days=offset)).strftime("%Y-%m-%d")
        for offset in range(0, 4)
    ]

    for day in dates:
        data = _api_get(
            "/fixtures",
            {
                "date": day,
                "timezone": TIMEZONE
            }
        )

        fixtures = data.get("response", []) or []
        print(f"📅 DATE {day} -> {len(fixtures)}")

        if fixtures:
            all_candidates.extend(fixtures)

            matches = _collect_from_fixtures(fixtures, allow_any_league=False)

            if matches:
                print(f"✅ MECZE: {len(matches)} | DATE={day}")
                print("🔎 SAMPLE:", matches[:3])
                return matches

    # 3) final fallback: any real league from collected fixtures
    if all_candidates:
        print("⚠️ TOP leagues empty in date scan -> fallback all real leagues")
        matches = _collect_from_fixtures(all_candidates, allow_any_league=True)

        if matches:
            print(f"✅ MECZE FALLBACK: {len(matches)}")
            print("🔎 SAMPLE:", matches[:3])
            return matches

    print("⚠️ NO MATCHES FOUND AFTER ALL FALLBACKS")
    print("✅ MECZE: 0")
    print("🔎 SAMPLE: []")

    return []


def get_odds_market_data(match):
    fixture_id = match.get("fixture_id")

    if not fixture_id:
        return None

    url = f"{BASE_URL}/odds"
    params = {"fixture": fixture_id}

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=25)
        print(f"🌐 API GET /odds fixture={fixture_id} -> HTTP {response.status_code}")

        data = response.json()

        errors = data.get("errors")
        if errors:
            print(f"❌ ODDS API ERRORS fixture={fixture_id}: {errors}")

        response_data = data.get("response")
        if not response_data:
            return None

        bookmakers = response_data[0].get("bookmakers", [])
        markets = {}

        for bookmaker in bookmakers:
            bookmaker_name = bookmaker.get("name") or bookmaker.get("title") or ""

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
