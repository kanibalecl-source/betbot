
"""Autonomous AI picks engine for KANIBAL ANALYTICS.

This module creates AI-owned picks in data/ai_picks.csv.
It does not place bets and does not modify bookmaker accounts.
It reads available match/feed/history files, scores candidates with the
learning history, and writes a separate AI decision output.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

AI_PICKS_FILE = DATA_DIR / "ai_picks.csv"
PREMATCH_FILE = DATA_DIR / "auto_all_picks.csv"
LIVE_FILE = DATA_DIR / "live_matches.csv"
RESULTS_FILE = DATA_DIR / "results_history.csv"
HISTORY_FILE = DATA_DIR / "history.csv"

AI_COLUMNS = [
    "ai_id", "created_at", "source", "league", "match", "market", "odds",
    "confidence", "edge", "ev", "ai_pick_score", "risk", "status",
    "tempo", "pressure", "momentum", "model_reason", "ai_generated"
]

MARKET_ROTATION = [
    "OVER_1.5", "BTTS_YES", "OVER_2.5", "DOUBLE_1X", "DOUBLE_X2", "OVER_0.5"
]


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        if path.exists() and path.stat().st_size > 0:
            return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame()


def _first(row, names: Iterable[str], default=""):
    for name in names:
        try:
            value = row.get(name)
        except Exception:
            value = None
        if value is not None and pd.notna(value) and str(value).strip() != "":
            return value
    return default


def _num(value, default: float = 0.0) -> float:
    try:
        return float(pd.to_numeric(pd.Series([value]), errors="coerce").fillna(default).iloc[0])
    except Exception:
        return float(default)


def _history_factor(results: pd.DataFrame, league: str, market: str) -> float:
    if results.empty:
        return 0.0
    df = results.copy()
    score = 0.0
    if "league" in df.columns:
        ldf = df[df["league"].astype(str).str.lower() == str(league).lower()]
        if not ldf.empty:
            score += min(8.0, len(ldf) * 0.25)
            if "roi" in ldf.columns:
                score += max(-8.0, min(10.0, _num(pd.to_numeric(ldf["roi"], errors="coerce").mean(), 0) / 2))
            if "profit" in ldf.columns:
                score += max(-6.0, min(8.0, _num(pd.to_numeric(ldf["profit"], errors="coerce").mean(), 0)))
    if "market" in df.columns:
        mdf = df[df["market"].astype(str).str.lower() == str(market).lower()]
        if not mdf.empty:
            score += min(6.0, len(mdf) * 0.20)
            if "roi" in mdf.columns:
                score += max(-6.0, min(8.0, _num(pd.to_numeric(mdf["roi"], errors="coerce").mean(), 0) / 2))
    return score


def _risk(score: float, edge: float, odds: float) -> str:
    if score >= 78 and edge >= 6 and odds <= 2.20:
        return "LOW"
    if score >= 64 and edge >= 2:
        return "MEDIUM"
    return "HIGH"


def _choose_market(row, idx: int, base_market: str, score_seed: float) -> str:
    # AI decision layer: selects its own market from features instead of copying the prematch pick.
    tempo = _num(_first(row, ["tempo", "pace", "xg_pace"], score_seed % 100), 0)
    pressure = _num(_first(row, ["pressure", "momentum", "dangerous_attacks"], score_seed % 100), 0)
    if pressure >= 75 or tempo >= 75:
        return "OVER_1.5"
    if pressure >= 62 and tempo >= 55:
        return "BTTS_YES"
    if score_seed >= 78:
        return "OVER_2.5"
    # Avoid simply cloning the PREMATCH market when possible.
    selected = MARKET_ROTATION[int(abs(score_seed + idx)) % len(MARKET_ROTATION)]
    if str(selected).upper() == str(base_market).upper():
        selected = MARKET_ROTATION[(MARKET_ROTATION.index(selected) + 1) % len(MARKET_ROTATION)]
    return selected


def _candidates() -> pd.DataFrame:
    frames = []
    live = _read_csv(LIVE_FILE)
    if not live.empty:
        live = live.copy()
        live["_ai_source"] = "LIVE_FEED"
        frames.append(live)
    prematch = _read_csv(PREMATCH_FILE)
    if not prematch.empty:
        prematch = prematch.copy()
        prematch["_ai_source"] = "PREMATCH_UNIVERSE"
        frames.append(prematch)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def build_ai_picks(limit: int = 12) -> pd.DataFrame:
    candidates = _candidates()
    results = pd.concat([_read_csv(RESULTS_FILE), _read_csv(HISTORY_FILE)], ignore_index=True, sort=False)
    if candidates.empty:
        return pd.DataFrame(columns=AI_COLUMNS)

    rows = []
    seen = set()
    now = datetime.now(timezone.utc).isoformat()
    for idx, row in candidates.iterrows():
        league = str(_first(row, ["league", "liga"], "-")).strip()
        match = str(_first(row, ["match", "mecz", "fixture"], "-")).strip()
        if not match or match == "-":
            continue
        key = (league.lower(), match.lower())
        if key in seen:
            continue
        seen.add(key)

        base_conf = _num(_first(row, ["confidence", "advanced_confidence", "ai_pick_score", "score"], 50), 50)
        base_edge = _num(_first(row, ["edge", "ev", "value"], 0), 0)
        odds = _num(_first(row, ["odds", "kurs_buk", "kurs"], 1.75), 1.75)
        base_market = str(_first(row, ["market", "typ", "signal"], "-")).strip().upper()
        tempo = _num(_first(row, ["tempo", "pace", "xg_pace"], min(100, 45 + base_conf * 0.35)), 0)
        pressure = _num(_first(row, ["pressure", "momentum", "dangerous_attacks"], min(100, 40 + base_conf * 0.40 + max(base_edge, 0))), 0)
        momentum = _num(_first(row, ["momentum"], min(100, (tempo + pressure) / 2)), 0)
        seed = base_conf * 0.55 + max(base_edge, 0) * 1.8 + tempo * 0.13 + pressure * 0.17
        market = _choose_market(row, idx, base_market, seed)
        hist = _history_factor(results, league, market)
        score = max(0, min(100, seed + hist))
        edge = max(0, min(35, base_edge + hist * 0.25 + (score - 60) * 0.08))
        ev = edge
        if score < 55:
            continue
        status = "AI PICK" if score >= 68 else "AI WATCH"
        risk = _risk(score, edge, odds)
        reason = (
            f"AI independent score={score:.1f}; market={market}; "
            f"tempo={tempo:.1f}; pressure={pressure:.1f}; history_factor={hist:.1f}"
        )
        ai_id = f"AI-{abs(hash((league, match, market, now[:10]))) % 10_000_000:07d}"
        rows.append({
            "ai_id": ai_id,
            "created_at": now,
            "source": _first(row, ["_ai_source"], "DATA_FEED"),
            "league": league,
            "match": match,
            "market": market,
            "odds": round(odds, 3),
            "confidence": round(score, 2),
            "edge": round(edge, 2),
            "ev": round(ev, 2),
            "ai_pick_score": round(score, 2),
            "risk": risk,
            "status": status,
            "tempo": round(tempo, 2),
            "pressure": round(pressure, 2),
            "momentum": round(momentum, 2),
            "model_reason": reason,
            "ai_generated": True,
        })

    out = pd.DataFrame(rows, columns=AI_COLUMNS)
    if not out.empty:
        out = out.sort_values(["ai_pick_score", "edge"], ascending=False).head(limit).reset_index(drop=True)
    return out


def run_once(limit: int = 12) -> int:
    DATA_DIR.mkdir(exist_ok=True)
    out = build_ai_picks(limit=limit)
    if out.empty:
        # Keep file valid for dashboard even when no candidates are available.
        out = pd.DataFrame(columns=AI_COLUMNS)
    out.to_csv(AI_PICKS_FILE, index=False)
    print(f"AI PICKS SAVED | rows={len(out)} | file={AI_PICKS_FILE}")
    return len(out)


if __name__ == "__main__":
    run_once()
