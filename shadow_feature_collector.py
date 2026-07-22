"""Collect contextual football features in shadow mode only.

Nothing from this module is read by bot.py.  The data can be evaluated later
with walk-forward tests before any explicit production integration.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    import requests
except Exception:
    requests = None

from agi_storage import conn, init_storage, log_event, now_iso
from prediction_quality_pipeline import _connect as evidence_connect, record_shadow_features

BASE_URL = "https://v3.football.api-sports.io"
API_KEY = os.getenv("APISPORTS_KEY") or os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY") or ""


def _parse(value: Any) -> Optional[datetime]:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)
        return result.astimezone(timezone.utc)
    except Exception:
        return None


def _api(endpoint: str, params: Dict[str, Any]) -> Optional[list]:
    if not API_KEY or requests is None:
        return None
    response = requests.get(
        f"{BASE_URL}/{endpoint}", headers={"x-apisports-key": API_KEY},
        params=params, timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("response")
    return data if isinstance(data, list) else None


def _historical_context(c, team: str, kickoff: datetime) -> Dict[str, Any]:
    rows = c.execute("""
        SELECT match_date, result, raw_json, home_team, away_team
        FROM picks_history
        WHERE status='CLOSED' AND match_date IS NOT NULL
          AND (lower(home_team)=lower(?) OR lower(away_team)=lower(?))
        ORDER BY match_date DESC LIMIT 20
    """, (team, team)).fetchall()
    prior = []
    seen_dates = set()
    for row in rows:
        when = _parse(row["match_date"])
        date_key = when.isoformat() if when else ""
        if when and when < kickoff and date_key not in seen_dates:
            seen_dates.add(date_key)
            prior.append((when, row))
    rest_days = None
    if prior:
        rest_days = round((kickoff - prior[0][0]).total_seconds() / 86400.0, 2)
    congestion_14d = sum(1 for when, _ in prior if (kickoff - when).total_seconds() <= 14 * 86400)
    return {"rest_days": rest_days, "matches_last_14d": congestion_14d}


def collect_shadow_features(limit: int = 25) -> Dict[str, Any]:
    init_storage()
    c = conn()
    rows = c.execute("""
        SELECT * FROM picks_history WHERE status='OPEN'
          AND fixture_id IS NOT NULL AND fixture_id != ''
          AND prediction_snapshot_id IS NOT NULL AND prediction_snapshot_id != ''
        ORDER BY match_date ASC LIMIT ?
    """, (max(1, int(limit)),)).fetchall()
    now = datetime.now(timezone.utc)
    captured = api_calls = errors = 0
    try:
        for row in rows:
            kickoff = _parse(row["match_date"])
            if kickoff is None or kickoff < now:
                continue
            home = str(row["home_team"] or "")
            away = str(row["away_team"] or "")
            try:
                evidence = evidence_connect()
                already = evidence.execute(
                    "SELECT 1 FROM shadow_feature_ledger WHERE snapshot_id=? AND substr(recorded_at,1,13)=?",
                    (row["prediction_snapshot_id"], now.isoformat()[:13]),
                ).fetchone()
                evidence.close()
            except Exception:
                already = None
            if already:
                continue
            home_history = _historical_context(c, home, kickoff)
            away_history = _historical_context(c, away, kickoff)
            minutes = (kickoff - now).total_seconds() / 60.0
            lineups = injuries = None
            # Expensive API context is queried only close to kickoff and is
            # never substituted when absent.
            if minutes <= 360 and API_KEY and requests is not None:
                try:
                    lineups = _api("fixtures/lineups", {"fixture": row["fixture_id"]})
                    injuries = _api("injuries", {"fixture": row["fixture_id"]})
                    api_calls += 2
                except Exception:
                    errors += 1
            values = {
                "home_rest_days": home_history["rest_days"],
                "away_rest_days": away_history["rest_days"],
                "home_matches_last_14d": home_history["matches_last_14d"],
                "away_matches_last_14d": away_history["matches_last_14d"],
                "lineups_available": True if lineups is not None else None,
                "lineups_count": len(lineups) if lineups is not None else None,
                "injuries_available": True if injuries is not None else None,
                "injuries_count": len(injuries) if injuries is not None else None,
                "home_form_home": None,
                "away_form_away": None,
                "coach_change": None,
            }
            available = sum(value is not None for value in values.values())
            result = record_shadow_features({
                "snapshot_id": row["prediction_snapshot_id"], "fixture_id": row["fixture_id"],
                "recorded_at": now_iso(), "kickoff": row["match_date"],
                "league": row["league"], "home_team": home, "away_team": away,
                "minutes_to_kickoff": round(minutes, 2), "source": "shadow_context_v1",
                "shadow_only": True, "used_by_production_model": False,
                "completeness": round(available / len(values), 6), **values,
            })
            if result.get("status") == "RECORDED":
                captured += 1
        payload = {"status": "OK", "checked": len(rows), "captured": captured,
                   "api_calls": api_calls, "errors": errors, "shadow_only": True}
        log_event("shadow_feature_collection", payload)
        return payload
    finally:
        c.close()


if __name__ == "__main__":
    print(json.dumps(collect_shadow_features(), ensure_ascii=False, indent=2))
