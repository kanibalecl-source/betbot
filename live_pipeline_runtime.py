from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import requests
from storage_paths import DATA_DIR

try:
    from config import API_FOOTBALL_KEY
except Exception:
    API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")

try:
    from advanced_live_engine import AdvancedLiveEngine
except Exception:
    AdvancedLiveEngine = None

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR.mkdir(exist_ok=True)
LIVE_FILE = DATA_DIR / "live_matches.csv"

LIVE_COLUMNS = [
    "fixture_id", "league", "match", "home", "away", "minute", "score", "status",
    "signal", "confidence", "odds", "value", "ev", "cashout", "stake", "risk", "source",
    "pressure", "momentum", "tempo", "xg_pace", "advanced_signal", "advanced_market",
    "advanced_confidence", "live_intensity", "updated_at"
]

FINISHED_STATUSES = {"FT", "AET", "PEN", "PST", "CANC", "ABD", "AWD", "WO"}
ACTIVE_STATUSES = {"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "INT"}


def ensure_live_file() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not LIVE_FILE.exists() or LIVE_FILE.stat().st_size == 0:
        pd.DataFrame(columns=LIVE_COLUMNS).to_csv(LIVE_FILE, index=False)


def _safe(value: Any, default: Any = "") -> Any:
    return default if value is None else value


def _is_active(status: str, minute: Any) -> bool:
    status = str(status or "").upper().strip()
    if status in FINISHED_STATUSES:
        return False
    if status in ACTIVE_STATUSES:
        return True
    try:
        return int(minute or 0) > 0 and int(minute or 0) < 130
    except Exception:
        return False


def fetch_live_matches() -> List[Dict[str, Any]]:
    if not API_FOOTBALL_KEY:
        print("⚠️ LIVE PIPELINE: API_FOOTBALL_KEY empty")
        return []

    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}

    try:
        response = requests.get(url, headers=headers, timeout=25)
        response.raise_for_status()
        payload = response.json().get("response", [])
    except Exception as exc:
        print(f"❌ LIVE PIPELINE FETCH ERROR: {exc}")
        return []

    rows: List[Dict[str, Any]] = []
    engine = AdvancedLiveEngine() if AdvancedLiveEngine else None

    for item in payload:
        try:
            fixture = item.get("fixture", {})
            teams = item.get("teams", {})
            goals = item.get("goals", {})
            league = item.get("league", {})
            status_obj = fixture.get("status", {})

            status = _safe(status_obj.get("short"), "LIVE")
            minute = _safe(status_obj.get("elapsed"), 0)

            if not _is_active(status, minute):
                continue

            home = _safe(teams.get("home", {}).get("name"), "")
            away = _safe(teams.get("away", {}).get("name"), "")
            home_goals = _safe(goals.get("home"), 0)
            away_goals = _safe(goals.get("away"), 0)

            base_match = {
                "fixture_id": fixture.get("id", ""),
                "league": _safe(league.get("name"), ""),
                "match": f"{home} - {away}",
                "home": home,
                "away": away,
                "minute": minute,
                "score": f"{home_goals}:{away_goals}",
                "status": status,
                "home_goals": home_goals,
                "away_goals": away_goals,
            }

            enriched: Dict[str, Any] = {}
            if engine:
                try:
                    enriched = engine.enrich_match(base_match, stats={})
                except Exception as exc:
                    print(f"⚠️ LIVE ENRICH ERROR: {exc}")
                    enriched = {}

            confidence = float(enriched.get("advanced_confidence", 0) or 0)
            signal = enriched.get("advanced_signal") or "LIVE MONITORING"
            value = float(enriched.get("live_edge", 0) or 0)
            risk = "HIGH" if confidence >= 80 else "MEDIUM" if confidence >= 60 else "LOW"

            rows.append({
                **base_match,
                "signal": signal,
                "confidence": confidence,
                "odds": "",
                "value": value,
                "ev": value,
                "cashout": "HOLD" if confidence >= 70 else "MONITOR",
                "stake": "",
                "risk": risk,
                "source": "LIVE API",
                "pressure": enriched.get("pressure_index", 0),
                "momentum": enriched.get("momentum_score_adv", 0),
                "tempo": enriched.get("tempo_score", 0),
                "xg_pace": enriched.get("xg_pace", 0),
                "advanced_signal": enriched.get("advanced_signal", ""),
                "advanced_market": enriched.get("advanced_market", ""),
                "advanced_confidence": confidence,
                "live_intensity": enriched.get("live_intensity", ""),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as exc:
            print(f"⚠️ LIVE ITEM PARSE ERROR: {exc}")

    return rows


def save_live_matches(rows: List[Dict[str, Any]]) -> None:
    ensure_live_file()
    df = pd.DataFrame(rows, columns=LIVE_COLUMNS)
    df.to_csv(LIVE_FILE, index=False)
    print(f"✅ LIVE PIPELINE SAVED | rows={len(df)} | file={LIVE_FILE}")


def run_once() -> int:
    rows = fetch_live_matches()
    save_live_matches(rows)
    return len(rows)


def main() -> None:
    interval = int(os.getenv("LIVE_LOOP_SECONDS", "60"))
    print(f"🚀 LIVE PIPELINE RUNTIME START | interval={interval}s")
    ensure_live_file()
    while True:
        try:
            count = run_once()
            print(f"💓 LIVE PIPELINE LOOP OK | active={count}")
        except Exception as exc:
            print(f"❌ LIVE PIPELINE LOOP ERROR: {exc}")
        time.sleep(max(15, interval))


if __name__ == "__main__":
    main()
