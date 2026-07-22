from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    import requests
except Exception:
    requests = None

from agi_storage import conn, init_storage, now_iso, export_history_csv, log_event

try:
    from api_results import get_closing_odds_safe
except Exception:
    get_closing_odds_safe = None

try:
    from prediction_quality_pipeline import record_closing_odds
except Exception:
    record_closing_odds = None

BASE_URL = "https://v3.football.api-sports.io"
API_KEY = os.getenv("APISPORTS_KEY") or os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY") or ""


def _headers() -> Dict[str, str]:
    return {"x-apisports-key": API_KEY.strip()}


def fetch_result(fixture_id: str) -> Optional[Dict[str, Any]]:
    if not API_KEY or not fixture_id or requests is None:
        return None
    r = requests.get(f"{BASE_URL}/fixtures", headers=_headers(), params={"id": fixture_id}, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data.get("response"):
        return None
    g = data["response"][0]
    status = str(g.get("fixture", {}).get("status", {}).get("short", ""))
    finished = status in {"FT", "AET", "PEN"}
    if not finished:
        return None
    hg = g.get("goals", {}).get("home")
    ag = g.get("goals", {}).get("away")
    if hg is None or ag is None:
        return None
    return {"home_goals": int(hg), "away_goals": int(ag), "status": status}


def evaluate_market(market: str, hg: int, ag: int) -> Optional[bool]:
    m = str(market or "").upper()
    total = hg + ag
    if m in {"HOME_WIN", "1"}: return hg > ag
    if m in {"DRAW", "X"}: return hg == ag
    if m in {"AWAY_WIN", "2"}: return ag > hg
    if m in {"DOUBLE_1X", "HOME_OR_DRAW", "1X"}: return hg >= ag
    if m in {"DOUBLE_X2", "AWAY_OR_DRAW", "X2"}: return ag >= hg
    if m in {"DOUBLE_12", "HOME_OR_AWAY", "12"}: return hg != ag
    if m == "BTTS_YES" or "BTTS" in m and "NO" not in m: return hg > 0 and ag > 0
    if m == "BTTS_NO": return hg == 0 or ag == 0
    if m.startswith("OVER_"):
        try: return total > float(m.split("_", 1)[1])
        except Exception: return None
    if m.startswith("UNDER_"):
        try: return total < float(m.split("_", 1)[1])
        except Exception: return None
    return None


def _raw(row: Any) -> Dict[str, Any]:
    try:
        payload = json.loads(row["raw_json"] or "{}")
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _parse_time(value: Any) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _fetch_closing_for_row(row: Any) -> Optional[float]:
    if not get_closing_odds_safe:
        return None
    raw = _raw(row)
    try:
        value = get_closing_odds_safe(
            fixture_id=row["fixture_id"],
            odds_event_id=row["odds_event_id"] or raw.get("odds_event_id"),
            home_team=row["home_team"],
            away_team=row["away_team"],
            market_key=row["odds_api_market"] or raw.get("odds_api_market") or "h2h",
            outcome_name=row["closing_outcome_name"] or raw.get("closing_outcome_name"),
        )
        number = float(value) if value not in (None, "") else None
        return number if number is not None and number > 1.0 else None
    except Exception as exc:
        log_event("closing_odds_error", {"id": row["id"], "error": str(exc)})
        return None


def capture_closing_odds_for_open_picks(limit: int = 100) -> Dict[str, int]:
    """Capture one near-kickoff quote; never use it as a model feature."""
    init_storage()
    c = conn()
    rows = c.execute("""
        SELECT * FROM picks_history
        WHERE status='OPEN' AND closing_odds IS NULL
          AND fixture_id IS NOT NULL AND fixture_id != ''
        ORDER BY match_date ASC LIMIT ?
    """, (max(1, int(limit)),)).fetchall()
    window_minutes = max(5, int(os.getenv("BETBOT_CLOSING_ODDS_WINDOW_MINUTES", "45")))
    checked = captured = 0
    now = datetime.now(timezone.utc)
    try:
        for row in rows:
            kickoff = _parse_time(row["match_date"])
            if kickoff is None:
                continue
            minutes = (kickoff - now).total_seconds() / 60.0
            if minutes < -10 or minutes > window_minutes:
                continue
            checked += 1
            closing = _fetch_closing_for_row(row)
            if closing is None:
                continue
            taken = float(row["odds"] or 0)
            clv = taken / closing - 1.0 if taken > 1.0 else None
            recorded_at = now_iso()
            c.execute("""
                UPDATE picks_history SET closing_odds=?, closing_odds_recorded_at=?, clv=?
                WHERE id=? AND closing_odds IS NULL
            """, (closing, recorded_at, clv, row["id"]))
            if record_closing_odds:
                record_closing_odds({
                    "snapshot_id": row["prediction_snapshot_id"],
                    "fixture_id": row["fixture_id"], "market": row["market"],
                    "bookmaker": _raw(row).get("bookmaker", ""),
                    "odds_taken": taken, "closing_odds": closing,
                    "recorded_at": recorded_at, "source": "near_kickoff_capture",
                })
            captured += 1
        c.commit()
        log_event("closing_odds_capture", {"checked": checked, "captured": captured})
        return {"checked": checked, "captured": captured}
    finally:
        c.close()


def settle_stored_picks(limit: int = 200) -> Dict[str, int]:
    init_storage()
    if not API_KEY:
        log_event("settlement_skipped", {"reason": "missing APISPORTS_KEY/FOOTBALL_API_KEY"})
        return {"checked": 0, "settled": 0, "skipped": 1}
    c = conn()
    rows = c.execute("""
        SELECT * FROM picks_history
        WHERE status='OPEN' AND fixture_id IS NOT NULL AND fixture_id != ''
        ORDER BY created_at ASC LIMIT ?
    """, (limit,)).fetchall()
    checked = 0
    settled = 0
    for row in rows:
        checked += 1
        try:
            res = fetch_result(str(row["fixture_id"]))
            if not res:
                continue
            won = evaluate_market(row["market"], res["home_goals"], res["away_goals"])
            if won is None:
                continue
            stake = float(row["stake"] or 1)
            odds = float(row["odds"] or 0)
            profit = stake * (odds - 1) if won else -stake
            roi = (profit / stake) * 100 if stake else 0
            result = "WIN" if won else "LOSE"
            closing = row["closing_odds"]
            if closing in (None, ""):
                closing = _fetch_closing_for_row(row)
            closing = float(closing) if closing not in (None, "") else None
            clv = odds / closing - 1.0 if closing is not None and closing > 1.0 and odds > 1.0 else None
            settled_at = now_iso()
            c.execute("""
                UPDATE picks_history SET updated_at=?, status='CLOSED', result=?, profit=?, roi=?,
                    closing_odds=COALESCE(closing_odds, ?), clv=?, settled_at=? WHERE id=?
            """, (settled_at, result, round(profit, 4), round(roi, 2), closing, clv, settled_at, row["id"]))
            if closing is not None and record_closing_odds:
                record_closing_odds({
                    "snapshot_id": row["prediction_snapshot_id"],
                    "fixture_id": row["fixture_id"], "market": row["market"],
                    "bookmaker": _raw(row).get("bookmaker", ""),
                    "odds_taken": odds, "closing_odds": closing,
                    "recorded_at": settled_at, "source": "settlement_fallback",
                })
            settled += 1
        except Exception as exc:
            log_event("settlement_error", {"id": row["id"], "error": str(exc)})
    c.commit()
    c.close()
    export_history_csv()
    log_event("settlement_cycle", {"checked": checked, "settled": settled})
    return {"checked": checked, "settled": settled, "skipped": 0}


if __name__ == "__main__":
    print(settle_stored_picks())
