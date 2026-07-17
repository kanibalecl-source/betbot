from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

try:
    from config import API_FOOTBALL_KEY
except Exception:
    API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")

from storage_paths import DATA_DIR

DATA_DIR.mkdir(exist_ok=True)
LIVE_FILE = DATA_DIR / "live_matches.csv"

API_BASE_URL = "https://v3.football.api-sports.io"
ACTIVE_STATUSES = {"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "INT", "SUSP"}

LIVE_COLUMNS = [
    "fixture_id", "league", "match", "home", "away", "minute", "score", "status",
    "home_goals", "away_goals", "signal", "signal_verified", "confidence", "odds",
    "odds_market", "odds_bookmaker", "odds_verified", "value", "ev", "cashout",
    "stake", "risk", "source", "data_status", "stats_verified", "pressure", "momentum",
    "tempo", "xg_pace", "advanced_signal", "advanced_market", "advanced_confidence",
    "live_intensity", "api_timestamp", "updated_at", "enrichment_error",
]


class LiveDataError(RuntimeError):
    """The live provider did not return a trustworthy response."""


def ensure_live_file() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not LIVE_FILE.exists() or LIVE_FILE.stat().st_size == 0:
        pd.DataFrame(columns=LIVE_COLUMNS).to_csv(LIVE_FILE, index=False)


def _nonempty(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text and text.lower() not in {"none", "nan"} else None


def _number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, str):
            value = value.replace("%", "").replace(",", ".").strip()
        return float(value)
    except (TypeError, ValueError):
        return None


def _api_response(path: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not API_FOOTBALL_KEY:
        raise LiveDataError("API_FOOTBALL_KEY is empty")

    response = requests.get(
        f"{API_BASE_URL}{path}",
        params=params,
        headers={"x-apisports-key": API_FOOTBALL_KEY},
        timeout=25,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise LiveDataError(f"Invalid JSON payload for {path}")

    errors = payload.get("errors")
    if errors:
        raise LiveDataError(f"Provider error for {path}: {errors}")

    rows = payload.get("response")
    if not isinstance(rows, list):
        raise LiveDataError(f"Missing response list for {path}")
    return rows


def _fixture_is_verified(item: Dict[str, Any]) -> bool:
    fixture = item.get("fixture") or {}
    teams = item.get("teams") or {}
    goals = item.get("goals") or {}
    status = fixture.get("status") or {}
    league = item.get("league") or {}

    status_short = _nonempty(status.get("short"))
    status_short = status_short.upper() if status_short else None
    minute = _number(status.get("elapsed"))
    return bool(
        fixture.get("id") is not None
        and status_short in ACTIVE_STATUSES
        and minute is not None
        and 0 <= minute < 130
        and _nonempty(teams.get("home", {}).get("name"))
        and _nonempty(teams.get("away", {}).get("name"))
        and _nonempty(league.get("name"))
        and _number(goals.get("home")) is not None
        and _number(goals.get("away")) is not None
    )


def _fetch_statistics(fixture_id: Any) -> Dict[str, Any]:
    response = _api_response("/fixtures/statistics", {"fixture": fixture_id})
    if len(response) < 2:
        return {}
    stats: Dict[str, Any] = {}
    for side, team in zip(("home", "away"), response[:2]):
        for entry in team.get("statistics") or []:
            name = _nonempty(entry.get("type"))
            if name and entry.get("value") is not None:
                stats[f"{side}_{name}"] = entry.get("value")
    return stats


def _fetch_one_real_live_odd(fixture_id: Any) -> Optional[Dict[str, Any]]:
    response = _api_response("/odds/live", {"fixture": fixture_id})
    for event in response:
        for bookmaker in event.get("bookmakers") or []:
            bookmaker_name = _nonempty(bookmaker.get("name"))
            for bet in bookmaker.get("bets") or []:
                bet_name = _nonempty(bet.get("name"))
                for price in bet.get("values") or []:
                    odd = _number(price.get("odd"))
                    selection = _nonempty(price.get("value"))
                    if bookmaker_name and bet_name and selection and odd and odd > 1.0:
                        return {
                            "odds": odd,
                            "market": f"{bet_name}: {selection}",
                            "bookmaker": bookmaker_name,
                        }
    return None


def fetch_live_matches() -> List[Dict[str, Any]]:
    payload = _api_response("/fixtures", {"live": "all"})
    fetched_at = datetime.now(timezone.utc).isoformat()
    enrich_limit = max(0, int(os.getenv("LIVE_ENRICH_LIMIT", "10")))
    rows: List[Dict[str, Any]] = []

    for item in payload:
        if not isinstance(item, dict) or not _fixture_is_verified(item):
            continue

        fixture = item["fixture"]
        teams = item["teams"]
        goals = item["goals"]
        league = item["league"]
        status_obj = fixture["status"]
        fixture_id = fixture["id"]
        home = str(teams["home"]["name"]).strip()
        away = str(teams["away"]["name"]).strip()
        minute = int(float(status_obj["elapsed"]))
        home_goals = int(float(goals["home"]))
        away_goals = int(float(goals["away"]))

        stats: Dict[str, Any] = {}
        real_odd: Optional[Dict[str, Any]] = None
        enrichment_error = ""
        if len(rows) < enrich_limit:
            try:
                stats = _fetch_statistics(fixture_id)
            except Exception as exc:
                enrichment_error = f"stats unavailable: {exc}"
            try:
                real_odd = _fetch_one_real_live_odd(fixture_id)
            except Exception as exc:
                suffix = f"odds unavailable: {exc}"
                enrichment_error = f"{enrichment_error}; {suffix}".strip("; ")

        odds_verified = bool(real_odd)
        data_status = "VERIFIED_FIXTURE_AND_ODDS" if odds_verified else "VERIFIED_FIXTURE_ONLY"

        rows.append({
            "fixture_id": fixture_id,
            "league": str(league["name"]).strip(),
            "match": f"{home} - {away}",
            "home": home,
            "away": away,
            "minute": minute,
            "score": f"{home_goals}:{away_goals}",
            "status": str(status_obj["short"]).strip().upper(),
            "home_goals": home_goals,
            "away_goals": away_goals,
            # A real fixture or a real bookmaker price is not automatically a betting pick.
            "signal": "",
            "signal_verified": False,
            "confidence": "",
            "odds": real_odd["odds"] if real_odd else "",
            "odds_market": real_odd["market"] if real_odd else "",
            "odds_bookmaker": real_odd["bookmaker"] if real_odd else "",
            "odds_verified": odds_verified,
            "value": "",
            "ev": "",
            "cashout": "",
            "stake": "",
            "risk": "",
            "source": "API-Football /fixtures?live=all",
            "data_status": data_status,
            "stats_verified": bool(stats),
            # These model fields remain empty until a validated model consumes complete real stats.
            "pressure": "",
            "momentum": "",
            "tempo": "",
            "xg_pace": "",
            "advanced_signal": "",
            "advanced_market": "",
            "advanced_confidence": "",
            "live_intensity": "",
            "api_timestamp": fixture.get("timestamp", ""),
            "updated_at": fetched_at,
            "enrichment_error": enrichment_error,
        })

    return rows


def save_live_matches(rows: List[Dict[str, Any]]) -> None:
    ensure_live_file()
    df = pd.DataFrame(rows)
    for column in LIVE_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    df = df[LIVE_COLUMNS]
    temp_file = LIVE_FILE.with_suffix(".csv.tmp")
    df.to_csv(temp_file, index=False)
    temp_file.replace(LIVE_FILE)
    print(f"LIVE PIPELINE SAVED | rows={len(df)} | file={LIVE_FILE}")


def run_once() -> int:
    # Fetch errors intentionally propagate. The scheduler logs the failure and the last valid file
    # remains untouched. A successful provider response with zero matches legitimately clears it.
    rows = fetch_live_matches()
    save_live_matches(rows)
    return len(rows)


def main() -> None:
    interval = int(os.getenv("LIVE_LOOP_SECONDS", "60"))
    print(f"LIVE PIPELINE RUNTIME START | interval={interval}s")
    ensure_live_file()
    while True:
        try:
            count = run_once()
            print(f"LIVE PIPELINE LOOP OK | active={count}")
        except Exception as exc:
            print(f"LIVE PIPELINE LOOP ERROR | previous_file_preserved=True | error={exc}")
        time.sleep(max(15, interval))


if __name__ == "__main__":
    main()
