import os
import requests
from datetime import datetime, timedelta, timezone
import re

from api_football_request_control import fetch_fixture_odds
from market_data_integrity_v13 import build_market_consensus

API_KEY = os.getenv("API_FOOTBALL_KEY", "")

BASE_URL = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": API_KEY
}

# Fail closed: football odds shown as "Buk" must come from a configured,
# identifiable bookmaker accepted for the Polish-facing product.  The list is
# deliberately configurable because provider coverage and licences can change.
DEFAULT_POLISH_BOOKMAKERS = (
    "superbet,sts,fortuna,betclic,etoto,forbet,totalbet,pzbuk"
)

# Only the full-match goals-total market is allowed to create OVER/UNDER keys.
# Substring matching is forbidden because provider feeds also contain team,
# half, corner and card totals with "Over/Under" in their names.
FULL_MATCH_TOTAL_BET_NAMES = {
    "goals over under",
    "over under",
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


def _normalized_token(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _normalized_bet_name(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()


def _allowed_football_bookmakers():
    configured = os.getenv(
        "BETBOT_FOOTBALL_BOOKMAKER_ALLOWLIST",
        DEFAULT_POLISH_BOOKMAKERS,
    )
    values = [item.strip() for item in str(configured or "").split(",") if item.strip()]
    if any(item == "*" for item in values):
        return None
    return {_normalized_token(item) for item in values if _normalized_token(item)}


def _bookmaker_is_allowed(bookmaker_name):
    allowed = _allowed_football_bookmakers()
    if allowed is None:
        return True
    return _normalized_token(bookmaker_name) in allowed


def _is_full_match_total_bet(market_name):
    return _normalized_bet_name(market_name) in FULL_MATCH_TOTAL_BET_NAMES


def _is_explicit_false(value):
    return value is False or str(value or "").strip().lower() in {"0", "false", "no", "off"}


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

    result = fetch_fixture_odds(
        fixture_id=fixture_id,
        url=url,
        headers=HEADERS,
        requester=getattr(requests, "get", None),
    )
    source = "CACHE" if result["cached"] else "API"
    print(
        f"ODDS STATUS: {result['status_code']} | fixture={fixture_id} | source={source}"
    )

    data = result["payload"]

    if data.get("errors"):
        print(f"ODDS API ERRORS: {data.get('errors')}")

    response_data = data.get("response")

    if not response_data:
        return []

    rows = []

    for bookmaker in response_data[0].get("bookmakers", []):

        bookmaker_name = str(bookmaker.get("name", "")).strip()
        bookmaker_id = bookmaker.get("id")

        if not bookmaker_name or not _bookmaker_is_allowed(bookmaker_name):
            continue

        for bet in bookmaker.get("bets", []):

            market_name = str(bet.get("name") or "").strip()
            bet_id = bet.get("id")

            for value in bet.get("values", []):

                # Some feeds expose parallel variants and mark the primary
                # quote explicitly.  Honour the marker when it is present.
                if "main" in value and _is_explicit_false(value.get("main")):
                    continue

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

                elif _is_full_match_total_bet(market_name):
                    line = _normalize_total_line(outcome)
                    if line in {"0.5", "1.5", "2.5", "3.5", "4.5"}:
                        if "Over" in outcome:
                            key = f"OVER_{line}"
                        elif "Under" in outcome:
                            key = f"UNDER_{line}"

                if key:
                    rows.append({
                        "market": key,
                        "odds": odd,
                        "bookmaker": bookmaker_name,
                        "bookmaker_id": bookmaker_id,
                        "bet_id": bet_id,
                        "bet_name": market_name,
                        "market_scope": "FULL_MATCH",
                        "observed_at": result["observed_at"],
                    })

    return rows


def get_odds_market_data(match):

    try:
        rows = _iter_fixture_odds(match)
        markets = {}
        groups = {
            "MATCH_WINNER": ("HOME_WIN", "DRAW", "AWAY_WIN"),
            "BTTS": ("BTTS_YES", "BTTS_NO"),
        }
        for line in ("0.5", "1.5", "2.5", "3.5", "4.5"):
            groups[f"TOTAL_{line}"] = (f"OVER_{line}", f"UNDER_{line}")

        allowlist = [
            item.strip()
            for item in os.getenv(
                "BETBOT_FOOTBALL_BOOKMAKER_ALLOWLIST",
                DEFAULT_POLISH_BOOKMAKERS,
            ).split(",")
            if item.strip() and item.strip() != "*"
        ]
        minimum_bookmakers = max(
            1, int(os.getenv("BETBOT_V13_FOOTBALL_MIN_BOOKMAKERS", "2"))
        )
        for group_name, outcomes in groups.items():
            group_rows = []
            for row in rows:
                original_market = str(row.get("market") or "").upper()
                if original_market not in outcomes:
                    continue
                group_rows.append(
                    {
                        **row,
                        "market": group_name,
                        "outcome": original_market,
                    }
                )
            if not group_rows:
                continue
            consensus = build_market_consensus(
                group_rows,
                sport="football",
                market=group_name,
                required_outcomes=outcomes,
                bookmaker_allowlist=allowlist or None,
                minimum_bookmakers=minimum_bookmakers,
            )
            if consensus.get("status") != "PASS":
                print(
                    "ODDS V13 QUARANTINE: "
                    f"{group_name} reason={consensus.get('reason')} "
                    f"rejected={consensus.get('rejected', {})}"
                )
                continue
            accepted = consensus.get("accepted_quotes", [])
            for outcome in outcomes:
                bookmaker = consensus["best_bookmakers"][outcome]
                best_row = next(
                    (
                        item
                        for item in accepted
                        if str(item.get("outcome")) == outcome
                        and str(item.get("bookmaker")) == bookmaker
                        and float(item.get("odds")) == float(
                            consensus["best_odds"][outcome]
                        )
                    ),
                    {},
                )
                by_bookmaker = {
                    name: float(values[outcome])
                    for name, values in consensus["by_bookmaker"].items()
                    if outcome in values
                }
                markets[outcome] = {
                    "best_odds": float(consensus["best_odds"][outcome]),
                    "bookmaker": bookmaker,
                    "bookmaker_id": consensus["best_bookmaker_ids"].get(outcome, ""),
                    "by_bookmaker": by_bookmaker,
                    "bookmaker_scope": "POLAND_ALLOWLIST",
                    "bookmaker_verified": True,
                    "bet_id": best_row.get("bet_id"),
                    "bet_name": best_row.get("bet_name"),
                    "market_scope": "FULL_MATCH",
                    "observed_at": consensus["observed_at"],
                    "market_integrity_schema": consensus["schema_version"],
                    "market_integrity_status": "PASS",
                    "market_consensus_id": consensus["consensus_id"],
                    "market_bookmaker_count": consensus["bookmaker_count"],
                    "market_probability": consensus["probabilities"][outcome],
                    "market_fair_odds": consensus["fair_odds"][outcome],
                    "market_probability_dispersion": consensus[
                        "probability_dispersion"
                    ],
                    "market_average_overround": consensus["average_overround"],
                    "market_rejected_quotes": consensus["rejected"],
                }

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
        for row in _iter_fixture_odds(match):
            if row["market"] != target_market:
                continue

            if wanted and wanted in str(row["bookmaker"]).lower():
                return row
            if not wanted:
                return row

        # Never label a price from a different bookmaker as the requested one.
        return None

    except Exception as e:
        print("BOOKMAKER ODDS ERROR:", e)
        return None

if __name__ == "__main__":

    matches = get_matches()

    print(f"FINAL MATCHES: {len(matches)}")
    print(matches[:3])
