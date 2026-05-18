"""Autonomous AI picks runtime for KANIBAL ANALYTICS.

Generates independent AI picks into data/ai_picks.csv.
This file does NOT place bets and does NOT log in to any bookmaker.
It uses real match/odds/live/history feeds and has a controlled bootstrap mode
so the AI tab is not dependent on PREMATCH picks.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

AI_PICKS_FILE = DATA_DIR / "ai_picks.csv"
AI_DEBUG_FILE = DATA_DIR / "ai_runtime_debug.json"
LIVE_FILE = DATA_DIR / "live_matches.csv"
RESULTS_FILE = DATA_DIR / "results_history.csv"
HISTORY_FILE = DATA_DIR / "history.csv"

AI_COLUMNS = [
    "ai_id", "created_at", "source", "league", "match", "fixture_id",
    "home", "away", "market", "odds", "confidence", "edge", "ev",
    "ai_pick_score", "risk", "status", "tempo", "pressure", "momentum",
    "model_reason", "ai_generated"
]

MARKET_ROTATION = ["OVER_1.5", "BTTS_YES", "OVER_2.5", "DOUBLE_1X", "DOUBLE_X2", "OVER_0.5"]


def _log(message: str) -> None:
    print(f"[AI_RUNTIME] {message}", flush=True)


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        if path.exists() and path.stat().st_size > 0:
            return pd.read_csv(path)
    except Exception as exc:
        _log(f"read error {path.name}: {exc}")
    return pd.DataFrame()


def _first(row: Any, names: Iterable[str], default: Any = "") -> Any:
    for name in names:
        try:
            value = row.get(name)
        except Exception:
            value = None
        if value is not None and pd.notna(value) and str(value).strip() != "":
            return value
    return default


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(pd.to_numeric(pd.Series([value]), errors="coerce").fillna(default).iloc[0])
    except Exception:
        return float(default)


def _is_active_status(status: Any, minute: Any) -> bool:
    s = str(status or "").upper().strip()
    if s in {"FT", "AET", "PEN", "PST", "CANC", "ABD", "AWD", "WO"}:
        return False
    if s in {"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "INT"}:
        return True
    try:
        m = int(float(minute or 0))
        return 0 < m < 130
    except Exception:
        return False


def _history_factor(results: pd.DataFrame, league: str, market: str) -> float:
    if results.empty:
        return 0.0
    score = 0.0
    df = results.copy()
    if "league" in df.columns:
        ldf = df[df["league"].astype(str).str.lower() == str(league).lower()]
        if not ldf.empty:
            score += min(8.0, len(ldf) * 0.20)
            for col, scale, lo, hi in [("roi", 2.0, -8.0, 10.0), ("profit", 1.0, -6.0, 8.0)]:
                if col in ldf.columns:
                    score += max(lo, min(hi, _num(pd.to_numeric(ldf[col], errors="coerce").mean(), 0) / scale))
    if "market" in df.columns:
        mdf = df[df["market"].astype(str).str.lower() == str(market).lower()]
        if not mdf.empty:
            score += min(6.0, len(mdf) * 0.18)
            if "roi" in mdf.columns:
                score += max(-6.0, min(8.0, _num(pd.to_numeric(mdf["roi"], errors="coerce").mean(), 0) / 2))
    return score


def _risk(score: float, edge: float, odds: float) -> str:
    if score >= 78 and edge >= 6 and (odds == 0 or odds <= 2.20):
        return "LOW"
    if score >= 64 and edge >= 2:
        return "MEDIUM"
    return "HIGH"


def _market_strength(market: str) -> float:
    market = str(market).upper()
    if market in {"OVER_1.5", "BTTS_YES", "DOUBLE_1X", "DOUBLE_X2"}:
        return 8.0
    if market in {"OVER_2.5", "OVER_0.5", "DOUBLE_12"}:
        return 5.0
    return 2.5


def _edge_from_odds(odds: float, confidence: float) -> float:
    if odds <= 1:
        return max(0.0, (confidence - 55) * 0.12)
    implied = 100.0 / odds
    # Conservative synthetic EV from AI confidence vs implied probability.
    return max(0.0, min(35.0, confidence - implied))


def _fixture_candidates_from_api() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    debug = {"api_matches": 0, "api_with_odds": 0, "api_no_odds": 0, "api_error": ""}
    rows: List[Dict[str, Any]] = []
    try:
        from data_api import get_matches, get_odds_market_data
    except Exception as exc:
        debug["api_error"] = f"import: {exc}"
        return rows, debug

    try:
        matches = get_matches() or []
        debug["api_matches"] = len(matches)
    except Exception as exc:
        debug["api_error"] = f"get_matches: {exc}"
        return rows, debug

    for idx, match in enumerate(matches):
        league = str(match.get("league", "-"))
        home = str(match.get("home") or match.get("home_team") or "")
        away = str(match.get("away") or match.get("away_team") or "")
        match_name = str(match.get("match") or f"{home} vs {away}").strip()
        fixture_id = match.get("fixture_id", "")
        minute = match.get("minute", "")
        status = match.get("status", "NS")

        odds_data: Dict[str, Dict[str, Any]] = {}
        try:
            odds_data = get_odds_market_data(match) or {}
        except Exception as exc:
            _log(f"odds error fixture={fixture_id}: {exc}")

        if odds_data:
            debug["api_with_odds"] += 1
            for market, meta in odds_data.items():
                try:
                    odds = float(meta.get("best_odds", 0))
                except Exception:
                    odds = 0.0
                rows.append({
                    "source": "AI_API_ODDS",
                    "league": league,
                    "match": match_name,
                    "fixture_id": fixture_id,
                    "home": home,
                    "away": away,
                    "market": str(market).upper(),
                    "odds": odds,
                    "minute": minute,
                    "status_raw": status,
                    "tempo": 52 + (idx % 7) * 3,
                    "pressure": 50 + (idx % 6) * 4,
                    "momentum": 50 + (idx % 5) * 5,
                })
        else:
            debug["api_no_odds"] += 1
            # Controlled bootstrap: still create an AI WATCH candidate from a real fixture.
            # This is not copied from PREMATCH; it is generated directly from fixtures.
            market = MARKET_ROTATION[idx % len(MARKET_ROTATION)]
            rows.append({
                "source": "AI_API_FIXTURE_BOOTSTRAP",
                "league": league,
                "match": match_name,
                "fixture_id": fixture_id,
                "home": home,
                "away": away,
                "market": market,
                "odds": 0.0,
                "minute": minute,
                "status_raw": status,
                "tempo": 48 + (idx % 8) * 3,
                "pressure": 46 + (idx % 7) * 4,
                "momentum": 47 + (idx % 6) * 5,
            })
    return rows, debug


def _live_candidates() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    debug = {"live_rows": 0, "live_active": 0}
    rows: List[Dict[str, Any]] = []
    live = _read_csv(LIVE_FILE)
    debug["live_rows"] = len(live)
    if live.empty:
        return rows, debug

    for idx, row in live.iterrows():
        minute = _first(row, ["minute"], 0)
        status = _first(row, ["status"], "LIVE")
        if not _is_active_status(status, minute):
            continue
        debug["live_active"] += 1
        home = str(_first(row, ["home"], ""))
        away = str(_first(row, ["away"], ""))
        match_name = str(_first(row, ["match"], f"{home} vs {away}"))
        rows.append({
            "source": "AI_LIVE_FEED",
            "league": str(_first(row, ["league"], "-")),
            "match": match_name,
            "fixture_id": _first(row, ["fixture_id"], ""),
            "home": home,
            "away": away,
            "market": str(_first(row, ["advanced_market", "signal", "market"], MARKET_ROTATION[idx % len(MARKET_ROTATION)])).upper(),
            "odds": _num(_first(row, ["odds"], 0), 0),
            "minute": minute,
            "status_raw": status,
            "tempo": _num(_first(row, ["tempo", "xg_pace"], 60), 60),
            "pressure": _num(_first(row, ["pressure", "confidence"], 60), 60),
            "momentum": _num(_first(row, ["momentum"], 60), 60),
        })
    return rows, debug


def _score_candidate(c: Dict[str, Any], idx: int, results: pd.DataFrame, bootstrap: bool) -> Dict[str, Any]:
    league = str(c.get("league", "-"))
    market = str(c.get("market") or MARKET_ROTATION[idx % len(MARKET_ROTATION)]).upper()
    odds = _num(c.get("odds"), 0)
    tempo = _num(c.get("tempo"), 50)
    pressure = _num(c.get("pressure"), 50)
    momentum = _num(c.get("momentum"), (tempo + pressure) / 2)

    hist = _history_factor(results, league, market)
    odds_component = 0.0
    if odds > 1:
        odds_component = max(-8.0, min(10.0, (odds - 1.65) * 8.0))

    score = (
        42.0
        + _market_strength(market)
        + tempo * 0.10
        + pressure * 0.16
        + momentum * 0.10
        + odds_component
        + hist
    )
    if bootstrap:
        score += 5.0

    score = max(0.0, min(100.0, score))
    edge = _edge_from_odds(odds, score)
    if odds <= 1 and bootstrap:
        edge = max(edge, 2.0 + (score - 52) * 0.08)

    status = "AI PICK" if score >= 64 else "AI WATCH"
    if score >= 76:
        status = "AI STRONG"

    reason = (
        f"Autonomous AI: source={c.get('source')}; market={market}; "
        f"tempo={tempo:.1f}; pressure={pressure:.1f}; momentum={momentum:.1f}; "
        f"history_factor={hist:.1f}; bootstrap={bootstrap}"
    )

    now = datetime.now(timezone.utc).isoformat()
    ai_id = f"AI-{abs(hash((league, c.get('match'), market, c.get('fixture_id'), now[:10]))) % 10_000_000:07d}"

    return {
        "ai_id": ai_id,
        "created_at": now,
        "source": c.get("source", "AI_FEED"),
        "league": league,
        "match": c.get("match", "-"),
        "fixture_id": c.get("fixture_id", ""),
        "home": c.get("home", ""),
        "away": c.get("away", ""),
        "market": market,
        "odds": round(odds, 3) if odds else "",
        "confidence": round(score, 2),
        "edge": round(edge, 2),
        "ev": round(edge, 2),
        "ai_pick_score": round(score, 2),
        "risk": _risk(score, edge, odds),
        "status": status,
        "tempo": round(tempo, 2),
        "pressure": round(pressure, 2),
        "momentum": round(momentum, 2),
        "model_reason": reason,
        "ai_generated": True,
    }


def build_ai_picks(limit: int = 12) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    results = pd.concat([_read_csv(RESULTS_FILE), _read_csv(HISTORY_FILE)], ignore_index=True, sort=False)
    bootstrap = len(results) < int(os.getenv("AI_BOOTSTRAP_MIN_HISTORY", "50"))

    live_rows, live_debug = _live_candidates()
    api_rows, api_debug = _fixture_candidates_from_api()

    # LIVE gets priority, API fixtures fill the rest. PREMATCH picks are intentionally not used.
    candidates = live_rows + api_rows
    debug = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "bootstrap": bootstrap,
        "candidate_count": len(candidates),
        "live": live_debug,
        "api": api_debug,
        "accepted": 0,
        "rejected_low_score": 0,
        "min_conf": None,
        "output": str(AI_PICKS_FILE),
    }

    if not candidates:
        return pd.DataFrame(columns=AI_COLUMNS), debug

    min_conf = float(os.getenv("AI_BOOTSTRAP_MIN_CONF" if bootstrap else "AI_PRODUCTION_MIN_CONF", "50" if bootstrap else "62"))
    debug["min_conf"] = min_conf

    rows: List[Dict[str, Any]] = []
    seen = set()
    for idx, candidate in enumerate(candidates):
        match_name = str(candidate.get("match", "")).strip()
        if not match_name or match_name == "-":
            continue
        key = (str(candidate.get("league", "")).lower(), match_name.lower(), str(candidate.get("market", "")).upper())
        if key in seen:
            continue
        seen.add(key)

        scored = _score_candidate(candidate, idx, results, bootstrap=bootstrap)
        if _num(scored["confidence"], 0) < min_conf:
            debug["rejected_low_score"] += 1
            continue
        rows.append(scored)

    out = pd.DataFrame(rows, columns=AI_COLUMNS)
    if not out.empty:
        out = out.sort_values(["ai_pick_score", "edge"], ascending=False).head(limit).reset_index(drop=True)
    debug["accepted"] = len(out)
    return out, debug


def run_once(limit: int = 12) -> int:
    DATA_DIR.mkdir(exist_ok=True)
    out, debug = build_ai_picks(limit=limit)
    if out.empty:
        out = pd.DataFrame(columns=AI_COLUMNS)
    out.to_csv(AI_PICKS_FILE, index=False)
    try:
        AI_DEBUG_FILE.write_text(json.dumps(debug, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    _log(f"AI PICKS SAVED | rows={len(out)} | candidates={debug.get('candidate_count')} | bootstrap={debug.get('bootstrap')} | file={AI_PICKS_FILE}")
    return len(out)


if __name__ == "__main__":
    run_once()
