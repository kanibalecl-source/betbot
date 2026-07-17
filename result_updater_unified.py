from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests

from agi_storage import conn, init_storage, now_iso, export_history_csv, log_event

BASE_URL = "https://v3.football.api-sports.io"
API_KEY = os.getenv("APISPORTS_KEY") or os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY") or ""


def _headers() -> Dict[str, str]:
    return {"x-apisports-key": API_KEY.strip()}


def fetch_result(fixture_id: str) -> Optional[Dict[str, Any]]:
    if not API_KEY or not fixture_id:
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
    return {
        "home_goals": int(hg),
        "away_goals": int(ag),
        "status": status,
        "fixture_id": str(fixture_id),
        "source": "API_FOOTBALL",
    }


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
    audit_events = []
    for row in rows:
        checked += 1
        try:
            res = fetch_result(str(row["fixture_id"]))
            if not res:
                continue
            won = evaluate_market(row["market"], res["home_goals"], res["away_goals"])
            if won is None:
                continue
            stake = float(row["stake"] or 0)
            odds = float(row["odds"] or 0)
            if stake <= 0 or odds <= 1:
                audit_events.append({
                    "event_type": "settlement_skipped",
                    "pick_key": row["pick_key"], "fixture_id": row["fixture_id"],
                    "reason": "missing_real_stake_or_odds", "stake": stake, "odds": odds,
                })
                continue
            profit = stake * (odds - 1) if won else -stake
            roi = (profit / stake) * 100 if stake else 0
            result = "WIN" if won else "LOSE"
            c.execute("""
                UPDATE picks_history SET updated_at=?, status='CLOSED', result=?, profit=?, roi=?,
                    home_goals=?, away_goals=?, result_score=?, settlement_source=?, settled_at=?
                WHERE id=? AND status='OPEN'
            """, (
                now_iso(), result, round(profit, 4), round(roi, 2),
                res["home_goals"], res["away_goals"],
                f"{res['home_goals']}:{res['away_goals']}", res["source"], now_iso(), row["id"]
            ))
            audit_events.append({
                "event_type": "pick_settled",
                "pick_key": row["pick_key"], "fixture_id": row["fixture_id"],
                "market": row["market"], "result": result,
                "score": f"{res['home_goals']}:{res['away_goals']}", "source": res["source"],
            })
            settled += 1
        except Exception as exc:
            log_event("settlement_error", {"id": row["id"], "error": str(exc)})
    c.commit()
    c.close()
    export_history_csv()
    for event in audit_events:
        event_type = event.pop("event_type", "settlement_audit")
        log_event(event_type, event)
    log_event("settlement_cycle", {"checked": checked, "settled": settled})
    return {"checked": checked, "settled": settled, "skipped": 0}


if __name__ == "__main__":
    print(settle_stored_picks())
