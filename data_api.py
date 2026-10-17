import os
import requests
from datetime import datetime, timedelta, timezone
import re
import unicodedata

from api_football_request_control import fetch_fixture_odds
from market_data_integrity_v13 import build_market_consensus

API_KEY = os.getenv("API_FOOTBALL_KEY", "")

BASE_URL = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": API_KEY
}

# Publication may use every identifiable bookmaker that survived the real-data
# consensus gate.  Operators can still narrow this list explicitly, but a
# legacy Polish-only setting must not silently block international quotes.
DEFAULT_PUBLICATION_BOOKMAKERS = "*"

# API-Football often has broad bookmaker coverage but does not guarantee a
# Polish-facing quote for every fixture.  The existing Odds API subscription is
# therefore used as a second, real-data source.  Responses are cached per
# competition so one bot cycle does not spend one request per fixture.
THE_ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"
THE_ODDS_API_CACHE = {}
THE_ODDS_API_LEAGUES = {
    39: "soccer_epl",
    140: "soccer_spain_la_liga",
    135: "soccer_italy_serie_a",
    78: "soccer_germany_bundesliga",
    61: "soccer_france_ligue_one",
    88: "soccer_netherlands_eredivisie",
    94: "soccer_portugal_primeira_liga",
    203: "soccer_turkey_super_league",
    106: "soccer_poland_ekstraklasa",
    2: "soccer_uefa_champs_league",
    3: "soccer_uefa_europa_league",
    71: "soccer_brazil_campeonato",
    128: "soccer_argentina_primera_division",
    218: "soccer_austria_bundesliga",
    119: "soccer_denmark_superliga",
    103: "soccer_norway_eliteserien",
    113: "soccer_sweden_allsvenskan",
}

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


def _normalized_team_name(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    words = re.findall(r"[a-z0-9]+", text.lower())
    removable = {"fc", "cf", "sc", "afc", "ac", "fk", "sk", "club"}
    return " ".join(word for word in words if word not in removable)


def _parse_utc(value):
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _the_odds_api_key():
    return (
        os.getenv("THE_ODDS_API_KEY", "").strip()
        or os.getenv("ODDS_API_KEY", "").strip()
    )


def _the_odds_api_events(sport_key):
    api_key = _the_odds_api_key()
    if not api_key or not sport_key:
        return []
    ttl = max(60, int(os.getenv("BETBOT_THE_ODDS_API_CACHE_SECONDS", "300")))
    cached = THE_ODDS_API_CACHE.get(sport_key)
    now = datetime.now(timezone.utc)
    if cached and (now - cached[0]).total_seconds() <= ttl:
        return cached[1]
    try:
        response = requests.get(
            f"{THE_ODDS_API_BASE_URL}/sports/{sport_key}/odds",
            params={
                "apiKey": api_key,
                "regions": os.getenv("BETBOT_THE_ODDS_API_REGIONS", "eu"),
                # The competition endpoint guarantees featured markets. BTTS
                # is an event-level additional market at The Odds API and must
                # not make the whole bulk request fail.
                "markets": "h2h,totals",
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            },
            timeout=25,
        )
        print(
            "THE ODDS API STATUS: "
            f"{response.status_code} | sport={sport_key} | "
            f"remaining={response.headers.get('x-requests-remaining', '?')}"
        )
        if response.status_code != 200:
            return []
        payload = response.json()
        events = payload if isinstance(payload, list) else []
        observed_at = now.isoformat()
        for event in events:
            if isinstance(event, dict):
                event["_betbot_observed_at"] = observed_at
        THE_ODDS_API_CACHE[sport_key] = (now, events)
        return events
    except Exception as exc:
        print(f"THE ODDS API ERROR: sport={sport_key} type={type(exc).__name__}")
        return []


def _matching_the_odds_event(match, events):
    home = _normalized_team_name(match.get("home") or match.get("home_team"))
    away = _normalized_team_name(match.get("away") or match.get("away_team"))
    kickoff = _parse_utc(match.get("match_date") or match.get("date"))
    if not home or not away or kickoff is None:
        return None
    matches = []
    for event in events:
        event_home = _normalized_team_name(event.get("home_team"))
        event_away = _normalized_team_name(event.get("away_team"))
        event_time = _parse_utc(event.get("commence_time"))
        if event_home != home or event_away != away or event_time is None:
            continue
        delta = abs((event_time - kickoff).total_seconds())
        if delta <= 12 * 60 * 60:
            matches.append((delta, event))
    # Fail closed on ambiguous event identity instead of guessing.
    if len(matches) != 1:
        if len(matches) > 1:
            print(f"THE ODDS API QUARANTINE: fixture={match.get('fixture_id')} ambiguous_event")
        return None
    return matches[0][1]


def _iter_the_odds_api_rows(match):
    try:
        league_id = int(match.get("league_id"))
    except (TypeError, ValueError):
        return []
    sport_key = THE_ODDS_API_LEAGUES.get(league_id)
    event = _matching_the_odds_event(match, _the_odds_api_events(sport_key))
    if not event:
        return []
    rows = []
    for bookmaker in event.get("bookmakers", []):
        bookmaker_name = str(bookmaker.get("title") or bookmaker.get("key") or "").strip()
        bookmaker_id = str(bookmaker.get("key") or "").strip()
        if not bookmaker_name:
            continue
        for market in bookmaker.get("markets", []):
            market_key = str(market.get("key") or "").strip().lower()
            provider_updated_at = market.get("last_update") or bookmaker.get("last_update")
            observed_at = event.get("_betbot_observed_at") or datetime.now(timezone.utc).isoformat()
            for outcome in market.get("outcomes", []):
                try:
                    odd = float(outcome.get("price"))
                except (TypeError, ValueError):
                    continue
                if odd <= 1:
                    continue
                name = str(outcome.get("name") or "").strip()
                key = None
                if market_key == "h2h":
                    if _normalized_team_name(name) == _normalized_team_name(event.get("home_team")):
                        key = "HOME_WIN"
                    elif _normalized_team_name(name) == _normalized_team_name(event.get("away_team")):
                        key = "AWAY_WIN"
                    elif name.lower() == "draw":
                        key = "DRAW"
                elif market_key == "totals":
                    try:
                        line = f"{float(outcome.get('point')):.1f}"
                    except (TypeError, ValueError):
                        line = ""
                    if line in {"0.5", "1.5", "2.5", "3.5", "4.5"} and name in {"Over", "Under"}:
                        key = f"{name.upper()}_{line}"
                elif market_key == "btts" and name.lower() in {"yes", "no"}:
                    key = f"BTTS_{name.upper()}"
                if key:
                    rows.append({
                        "market": key,
                        "odds": odd,
                        "bookmaker": bookmaker_name,
                        # Consensus independence is bookmaker-based, not
                        # provider-based. The same bookmaker received through
                        # two APIs must never count as two independent sources.
                        "bookmaker_id": f"bookmaker:{_normalized_token(bookmaker_name)}",
                        "provider_bookmaker_id": bookmaker_id,
                        "bet_id": market_key,
                        "bet_name": market_key,
                        "market_scope": "FULL_MATCH",
                        "observed_at": observed_at,
                        "provider_updated_at": provider_updated_at,
                        "odds_provider": "THE_ODDS_API",
                        "odds_event_id": event.get("id", ""),
                    })
    print(
        f"THE ODDS API MATCH: fixture={match.get('fixture_id')} "
        f"event={event.get('id')} quotes={len(rows)}"
    )
    return rows


def _normalized_bet_name(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()


def _allowed_football_bookmakers():
    configured = os.getenv(
        "BETBOT_FOOTBALL_PUBLICATION_BOOKMAKER_ALLOWLIST",
        DEFAULT_PUBLICATION_BOOKMAKERS,
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


def _football_consensus_bookmakers():
    """Return the independent sources allowed to confirm market quality.

    Publication and consensus are deliberately separate concerns:
    ``BETBOT_FOOTBALL_PUBLICATION_BOOKMAKER_ALLOWLIST`` optionally controls
    which identifiable bookmaker may be shown to the user, while this list controls which
    identifiable provider bookmakers may contribute to the two-source market
    consensus.  ``*`` keeps all named API-Football bookmakers eligible; the
    integrity layer still requires complete, aligned and non-outlying markets.
    """
    configured = os.getenv(
        "BETBOT_FOOTBALL_CONSENSUS_BOOKMAKER_ALLOWLIST",
        "*",
    )
    values = [item.strip() for item in str(configured or "").split(",") if item.strip()]
    if not values or any(item == "*" for item in values):
        return None
    return values


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


def _iter_fixture_odds(match, publication_only=True):

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

        if not bookmaker_name:
            continue
        # Existing callers receive only publishable Polish-facing quotes.
        # The consensus path opts in to all identifiable provider sources and
        # applies the publication allowlist after the integrity gate.
        if publication_only and not _bookmaker_is_allowed(bookmaker_name):
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
                        "bookmaker_id": f"bookmaker:{_normalized_token(bookmaker_name)}",
                        "provider_bookmaker_id": bookmaker_id,
                        "bet_id": bet_id,
                        "bet_name": market_name,
                        "market_scope": "FULL_MATCH",
                        "observed_at": result["observed_at"],
                    })

    return rows


def get_odds_market_data(match):

    try:
        rows = _iter_fixture_odds(match, publication_only=False)
        # Merge two independent real-data feeds.  Missing keys or unmatched
        # event identities simply keep the original fail-closed behaviour.
        rows.extend(_iter_the_odds_api_rows(match))
        markets = {}
        groups = {
            "MATCH_WINNER": ("HOME_WIN", "DRAW", "AWAY_WIN"),
            "BTTS": ("BTTS_YES", "BTTS_NO"),
        }
        for line in ("0.5", "1.5", "2.5", "3.5", "4.5"):
            groups[f"TOTAL_{line}"] = (f"OVER_{line}", f"UNDER_{line}")

        consensus_allowlist = _football_consensus_bookmakers()
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
                bookmaker_allowlist=consensus_allowlist,
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
                publication_quotes = [
                    item
                    for item in accepted
                    if str(item.get("outcome")) == outcome
                    and _bookmaker_is_allowed(item.get("bookmaker"))
                ]
                if not publication_quotes:
                    print(
                        "ODDS V13 PUBLICATION QUARANTINE: "
                        f"{outcome} reason=NO_ALLOWED_BOOKMAKER_QUOTE "
                        f"consensus_bookmakers={consensus['bookmaker_count']}"
                    )
                    continue
                best_row = max(
                    publication_quotes,
                    key=lambda item: float(item.get("odds") or 0),
                )
                bookmaker = str(best_row.get("bookmaker") or "").strip()
                by_bookmaker = {
                    name: float(values[outcome])
                    for name, values in consensus["by_bookmaker"].items()
                    if outcome in values and _bookmaker_is_allowed(name)
                }
                markets[outcome] = {
                    "best_odds": float(best_row["odds"]),
                    "bookmaker": bookmaker,
                    "bookmaker_id": best_row.get("bookmaker_id", ""),
                    "by_bookmaker": by_bookmaker,
                    "bookmaker_scope": "VERIFIED_PROVIDER_BOOKMAKER",
                    "bookmaker_verified": True,
                    "consensus_bookmaker_scope": (
                        "CONFIGURED_ALLOWLIST"
                        if consensus_allowlist is not None
                        else "ALL_IDENTIFIABLE_PROVIDER_BOOKMAKERS"
                    ),
                    "publication_separated_from_consensus": True,
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
