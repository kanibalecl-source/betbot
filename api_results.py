import os
from datetime import datetime
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _get_key(name):
    # 1. environment / .env
    value = os.getenv(name)
    if value:
        return value

    # 2. secrets_config.py
    try:
        import secrets_config
        value = getattr(secrets_config, name, "")
        if value:
            return value
    except Exception:
        pass

    # 3. existing data_api.py
    try:
        import data_api
        value = getattr(data_api, name, "")
        if value:
            return value
    except Exception:
        pass

    return ""


API_FOOTBALL_KEY = _get_key("API_FOOTBALL_KEY")
ODDS_API_KEY = _get_key("ODDS_API_KEY")


def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return None


def get_match_result_by_id(fixture_id):
    """
    Źródło: API-Football.
    Wymaga API_FOOTBALL_KEY.

    Zwraca:
    {
        "finished": True/False,
        "home_goals": int,
        "away_goals": int,
        "status": "FT",
        "fixture_id": "..."
    }
    """

    if not fixture_id or not API_FOOTBALL_KEY:
        return None

    url = "https://v3.football.api-sports.io/fixtures"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"id": fixture_id}

    try:
        r = requests.get(url, headers=headers, params=params, timeout=20)
        data = _safe_json(r)
    except Exception:
        return None

    if not data or not data.get("response"):
        return None

    match = data["response"][0]
    status = match["fixture"]["status"]["short"]

    return {
        "finished": status in {"FT", "AET", "PEN"},
        "home_goals": match["goals"]["home"],
        "away_goals": match["goals"]["away"],
        "status": status,
        "fixture_id": str(fixture_id)
    }


def _extract_best_outcome_price(odds_payload, target_outcome_name=None):
    prices = []

    for bookmaker in odds_payload.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            for outcome in market.get("outcomes", []):
                if target_outcome_name:
                    if outcome.get("name", "").lower() != target_outcome_name.lower():
                        continue

                price = outcome.get("price")
                if price:
                    try:
                        prices.append(float(price))
                    except Exception:
                        pass

    return max(prices) if prices else None


def _extract_outcome_quote(odds_payload, target_outcome_name=None, bookmaker_name=None):
    """Return a traceable quote, preferring the decision-time bookmaker."""
    quotes = []
    wanted_book = str(bookmaker_name or "").strip().lower()
    for bookmaker in odds_payload.get("bookmakers", []):
        book_title = str(bookmaker.get("title") or bookmaker.get("key") or "")
        for market in bookmaker.get("markets", []):
            for outcome in market.get("outcomes", []):
                name = str(outcome.get("name") or "")
                if target_outcome_name and name.lower() != str(target_outcome_name).lower():
                    continue
                try:
                    price = float(outcome.get("price"))
                except (TypeError, ValueError):
                    continue
                if price <= 1.0:
                    continue
                same_book = bool(wanted_book and wanted_book in book_title.lower())
                quotes.append({
                    "odds": price, "bookmaker": book_title,
                    "outcome_name": name, "same_bookmaker": same_book,
                    "market_key": str(market.get("key") or ""),
                    "last_update": str(bookmaker.get("last_update") or ""),
                })
    if not quotes:
        return None
    if wanted_book:
        matching = [quote for quote in quotes if quote["same_bookmaker"]]
        # Never silently mix bookmakers in CLV evidence.
        return max(matching, key=lambda quote: quote["odds"]) if matching else None
    return max(quotes, key=lambda quote: quote["odds"])


def get_closing_odds_by_odds_event_id(odds_event_id, market_key="h2h", outcome_name=None):
    """
    Źródło: The Odds API.
    Używa ID eventu z The Odds API, nie zawsze tego samego co API-Football.
    """

    if not odds_event_id or not ODDS_API_KEY:
        return None

    url = f"https://api.the-odds-api.com/v4/sports/soccer/events/{odds_event_id}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",
        "markets": market_key,
        "oddsFormat": "decimal",
    }

    try:
        r = requests.get(url, params=params, timeout=20)
        data = _safe_json(r)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    return _extract_best_outcome_price(data, outcome_name)


def find_odds_event_by_teams(home_team, away_team, commence_date=None, sport_key="soccer", market_key="h2h"):
    """
    Fallback dla The Odds API.
    Szuka eventu po nazwach drużyn, bo The Odds API zwykle nie używa fixture_id z API-Football.
    """

    if not ODDS_API_KEY or not home_team or not away_team:
        return None

    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",
        "markets": market_key,
        "oddsFormat": "decimal",
    }

    try:
        r = requests.get(url, params=params, timeout=25)
        data = _safe_json(r)
    except Exception:
        return None

    if not isinstance(data, list):
        return None

    h = str(home_team).lower().strip()
    a = str(away_team).lower().strip()

    for event in data:
        teams = [str(t).lower().strip() for t in event.get("teams", [])]
        home = str(event.get("home_team", "")).lower().strip()
        away = str(event.get("away_team", "")).lower().strip()

        direct_match = (h == home and a == away) or (h in teams and a in teams)

        if direct_match:
            return event

    return None


def get_closing_odds_safe(fixture_id=None, odds_event_id=None, home_team=None, away_team=None, market_key="h2h", outcome_name=None):
    """
    Najpierw próbuje po odds_event_id.
    Potem fallback po drużynach.
    fixture_id zapisujemy głównie do wyników przez API-Football.
    """

    odds = get_closing_odds_by_odds_event_id(
        odds_event_id=odds_event_id,
        market_key=market_key,
        outcome_name=outcome_name
    )
    if odds:
        return odds

    event = find_odds_event_by_teams(home_team, away_team, market_key=market_key)
    if not event:
        return None

    return _extract_best_outcome_price(event, outcome_name)


def get_odds_quote_safe(odds_event_id=None, home_team=None, away_team=None,
                        market_key="h2h", outcome_name=None, bookmaker_name=None):
    """Traceable version used by the evidence collector; prediction logic never calls it."""
    payload = None
    if odds_event_id and ODDS_API_KEY:
        url = f"https://api.the-odds-api.com/v4/sports/soccer/events/{odds_event_id}/odds"
        params = {"apiKey": ODDS_API_KEY, "regions": "eu", "markets": market_key,
                  "oddsFormat": "decimal"}
        try:
            payload = _safe_json(requests.get(url, params=params, timeout=20))
        except Exception:
            payload = None
    if not isinstance(payload, dict):
        payload = find_odds_event_by_teams(home_team, away_team, market_key=market_key)
    if not isinstance(payload, dict):
        return None
    quote = _extract_outcome_quote(payload, outcome_name, bookmaker_name)
    if quote:
        quote.update({"event_id": str(payload.get("id") or odds_event_id or "")})
    return quote
