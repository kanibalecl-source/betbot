"""Full self-learning runtime for KANIBAL ANALYTICS.

This module runs in the background scheduler and closes the loop:
AI picks -> settlement/history -> feature store -> adaptive model state -> new AI picks.
It does not place bets and it does not connect to bookmaker accounts.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd
from storage_paths import DATA_DIR

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR.mkdir(exist_ok=True)

PREMATCH_FILE = DATA_DIR / "auto_all_picks.csv"
LIVE_FILE = DATA_DIR / "live_matches.csv"
AI_PICKS_FILE = DATA_DIR / "ai_picks.csv"
RESULTS_FILE = DATA_DIR / "results_history.csv"
HISTORY_FILE = DATA_DIR / "history.csv"
CLV_FILE = DATA_DIR / "clv_history.csv"

AI_MODEL_DIR = DATA_DIR / "ai_learning"
AI_MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_STATE_FILE = AI_MODEL_DIR / "ai_model_state.json"
FEATURE_STORE_FILE = AI_MODEL_DIR / "ai_feature_store.csv"
EVENT_LOG_FILE = AI_MODEL_DIR / "ai_learning_events.csv"
DEBUG_FILE = DATA_DIR / "ai_runtime_debug.json"

AI_COLUMNS = [
    "ai_id", "created_at", "source", "league", "match", "market", "odds",
    "confidence", "edge", "ev", "ai_pick_score", "risk", "status",
    "tempo", "pressure", "momentum", "model_reason", "ai_generated"
]

FEATURE_COLUMNS = [
    "created_at", "league", "match", "market", "odds", "confidence", "edge",
    "ev", "tempo", "pressure", "momentum", "risk", "source", "result",
    "profit", "roi"
]

DEFAULT_STATE: Dict[str, Any] = {
    "version": "self_learning_v1",
    "created_at": None,
    "updated_at": None,
    "cycles": 0,
    "samples": 0,
    "settled_samples": 0,
    "mode": "BOOTSTRAP",
    "min_confidence": 54.0,
    "min_edge": 0.0,
    "league_weights": {},
    "market_weights": {},
    "risk_weights": {"LOW": 4.0, "MEDIUM": 1.5, "HIGH": -3.0},
    "last_summary": {},
}

MARKETS = ["OVER_1.5", "BTTS_YES", "OVER_2.5", "DOUBLE_1X", "DOUBLE_X2", "OVER_0.5", "BTTS_NO", "UNDER_4.5"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv(path: Path) -> pd.DataFrame:
    try:
        if path.exists() and path.stat().st_size > 0:
            return pd.read_csv(path)
    except Exception:
        pass
    return pd.DataFrame()


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state() -> Dict[str, Any]:
    if MODEL_STATE_FILE.exists():
        try:
            state = json.loads(MODEL_STATE_FILE.read_text(encoding="utf-8"))
            merged = dict(DEFAULT_STATE)
            merged.update(state)
            return merged
        except Exception:
            pass
    state = dict(DEFAULT_STATE)
    state["created_at"] = now_iso()
    state["updated_at"] = now_iso()
    write_json(MODEL_STATE_FILE, state)
    return state


def save_state(state: Dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    write_json(MODEL_STATE_FILE, state)


def first(row: Any, names: Iterable[str], default: Any = "") -> Any:
    for name in names:
        try:
            value = row.get(name)
        except Exception:
            value = None
        if value is not None and pd.notna(value) and str(value).strip() != "":
            return value
    return default


def num(value: Any, default: float = 0.0) -> float:
    try:
        out = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(default).iloc[0]
        return float(out)
    except Exception:
        return float(default)


def normalize_market(raw: Any) -> str:
    s = str(raw or "").strip().upper().replace(" ", "_").replace("-", "_")
    aliases = {
        "OVER_1.5": "OVER_1.5", "OVER_15": "OVER_1.5", "OVER1.5": "OVER_1.5",
        "OVER_2.5": "OVER_2.5", "OVER_25": "OVER_2.5", "OVER2.5": "OVER_2.5",
        "BTTS_YES": "BTTS_YES", "BTTS_TAK": "BTTS_YES", "BTTSYES": "BTTS_YES",
        "BTTS_NO": "BTTS_NO", "BTTS_NIE": "BTTS_NO", "BTTSNO": "BTTS_NO",
        "X2": "DOUBLE_X2", "DOUBLE_X2": "DOUBLE_X2", "1X": "DOUBLE_1X", "DOUBLE_1X": "DOUBLE_1X",
        "UNDER_4.5": "UNDER_4.5", "UNDER_45": "UNDER_4.5",
    }
    return aliases.get(s, s if s else "OVER_1.5")


def combine_results() -> pd.DataFrame:
    frames = [read_csv(RESULTS_FILE), read_csv(HISTORY_FILE)]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def result_score(value: Any) -> float:
    s = str(value or "").strip().lower()
    if any(x in s for x in ["win", "won", "wygr", "traf", "1", "true"]):
        return 1.0
    if any(x in s for x in ["loss", "lose", "przeg", "lost", "0", "false"]):
        return -1.0
    if "push" in s or "void" in s or "zwrot" in s:
        return 0.0
    return 0.0


def compute_weights(results: pd.DataFrame) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, Any]]:
    league_weights: Dict[str, float] = {}
    market_weights: Dict[str, float] = {}
    summary: Dict[str, Any] = {"rows": int(len(results)), "leagues": 0, "markets": 0}
    if results.empty:
        return league_weights, market_weights, summary

    df = results.copy()
    if "league" not in df.columns and "liga" in df.columns:
        df["league"] = df["liga"]
    if "market" not in df.columns and "typ" in df.columns:
        df["market"] = df["typ"]
    if "result_score" not in df.columns:
        if "result" in df.columns:
            df["result_score"] = df["result"].apply(result_score)
        else:
            df["result_score"] = 0.0
    if "profit" not in df.columns:
        df["profit"] = 0.0
    if "roi" not in df.columns:
        df["roi"] = 0.0

    def group_weight(g: pd.DataFrame) -> float:
        n = len(g)
        rs = pd.to_numeric(g.get("result_score", pd.Series([0]*n)), errors="coerce").fillna(0).mean()
        profit = pd.to_numeric(g.get("profit", pd.Series([0]*n)), errors="coerce").fillna(0).mean()
        roi = pd.to_numeric(g.get("roi", pd.Series([0]*n)), errors="coerce").fillna(0).mean()
        sample_bonus = min(8.0, n * 0.25)
        return round(max(-18.0, min(22.0, rs * 12.0 + profit * 1.5 + roi * 0.18 + sample_bonus)), 3)

    if "league" in df.columns:
        for league, g in df.groupby(df["league"].astype(str)):
            if league and league != "nan":
                league_weights[league] = group_weight(g)
    if "market" in df.columns:
        df["market_norm"] = df["market"].apply(normalize_market)
        for market, g in df.groupby("market_norm"):
            if market and market != "nan":
                market_weights[market] = group_weight(g)
    summary.update({"leagues": len(league_weights), "markets": len(market_weights)})
    return league_weights, market_weights, summary


def update_learning_state() -> Dict[str, Any]:
    state = load_state()
    results = combine_results()
    league_weights, market_weights, summary = compute_weights(results)
    state["cycles"] = int(state.get("cycles", 0)) + 1
    state["samples"] = int(len(read_csv(FEATURE_STORE_FILE))) if FEATURE_STORE_FILE.exists() else 0
    state["settled_samples"] = int(len(results))
    state["league_weights"] = league_weights
    state["market_weights"] = market_weights
    # Bootstrap until enough settled samples exist. Then tighten thresholds automatically.
    if len(results) < 30:
        state["mode"] = "BOOTSTRAP"
        state["min_confidence"] = 54.0
        state["min_edge"] = 0.0
    elif len(results) < 100:
        state["mode"] = "LEARNING"
        state["min_confidence"] = 60.0
        state["min_edge"] = 1.0
    else:
        state["mode"] = "PRODUCTION"
        state["min_confidence"] = 66.0
        state["min_edge"] = 2.0
    state["last_summary"] = summary
    save_state(state)
    return state


def candidates() -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    live = read_csv(LIVE_FILE)
    if not live.empty:
        live = live.copy()
        live["_source"] = "LIVE_FEED"
        frames.append(live)
    pre = read_csv(PREMATCH_FILE)
    if not pre.empty:
        pre = pre.copy()
        pre["_source"] = "FIXTURE_UNIVERSE"
        frames.append(pre)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def choose_market(row: Any, idx: int, state: Dict[str, Any], seed: float) -> str:
    market_weights = state.get("market_weights", {}) or {}
    tempo = num(first(row, ["tempo", "pace", "xg_pace"], 0), 0)
    pressure = num(first(row, ["pressure", "momentum", "dangerous_attacks"], 0), 0)
    base_market = normalize_market(first(row, ["market", "typ", "signal"], ""))
    weighted = sorted(MARKETS, key=lambda m: market_weights.get(m, 0), reverse=True)
    if pressure >= 78 or tempo >= 78:
        pref = "OVER_1.5"
    elif pressure >= 64 and tempo >= 55:
        pref = "BTTS_YES"
    elif seed >= 78:
        pref = "OVER_2.5"
    else:
        pref = weighted[idx % len(weighted)] if weighted else MARKETS[idx % len(MARKETS)]
    # This is an autonomous decision. It may use the fixture universe, but it does not blindly copy the prematch market.
    if pref == base_market and len(weighted) > 1:
        alt = weighted[(weighted.index(pref) + 1) % len(weighted)] if pref in weighted else MARKETS[(MARKETS.index(pref)+1) % len(MARKETS)]
        return alt
    return pref


def risk_for(score: float, edge: float, odds: float) -> str:
    if score >= 78 and edge >= 5 and odds <= 2.35:
        return "LOW"
    if score >= 63 and edge >= 1:
        return "MEDIUM"
    return "HIGH"


def build_ai_picks(limit: int = 12) -> pd.DataFrame:
    state = update_learning_state()
    cand = candidates()
    debug: Dict[str, Any] = {
        "updated_at": now_iso(),
        "mode": state.get("mode"),
        "candidates": int(len(cand)),
        "accepted": 0,
        "rejected": [],
        "min_confidence": state.get("min_confidence"),
        "min_edge": state.get("min_edge"),
    }
    if cand.empty:
        write_json(DEBUG_FILE, debug)
        return pd.DataFrame(columns=AI_COLUMNS)

    league_weights = state.get("league_weights", {}) or {}
    market_weights = state.get("market_weights", {}) or {}
    rows: List[Dict[str, Any]] = []
    features: List[Dict[str, Any]] = []
    seen = set()
    ts = now_iso()
    for idx, row in cand.iterrows():
        league = str(first(row, ["league", "liga"], "-")).strip()
        match = str(first(row, ["match", "mecz", "fixture"], "")).strip()
        if not match:
            home = str(first(row, ["home", "home_team"], "")).strip()
            away = str(first(row, ["away", "away_team"], "")).strip()
            match = f"{home} vs {away}" if home or away else ""
        if not match:
            debug["rejected"].append({"idx": int(idx), "reason": "no_match_name"})
            continue
        key = (league.lower(), match.lower())
        if key in seen:
            continue
        seen.add(key)

        base_conf = num(first(row, ["confidence", "advanced_confidence", "score", "ai_pick_score"], 52), 52)
        base_edge = num(first(row, ["edge", "ev", "value"], 0), 0)
        odds = num(first(row, ["odds", "kurs_buk", "kurs"], 1.75), 1.75)
        tempo = num(first(row, ["tempo", "pace", "xg_pace"], min(100, 35 + base_conf * 0.45)), 0)
        pressure = num(first(row, ["pressure", "momentum", "dangerous_attacks"], min(100, 35 + base_conf * 0.42 + max(base_edge, 0))), 0)
        momentum = num(first(row, ["momentum"], (tempo + pressure) / 2), 0)
        league_w = float(league_weights.get(league, 0.0))
        seed = base_conf * 0.58 + max(base_edge, 0) * 1.45 + tempo * 0.13 + pressure * 0.18 + league_w
        market = choose_market(row, idx, state, seed)
        market_w = float(market_weights.get(market, 0.0))
        score = max(0.0, min(100.0, seed + market_w))
        edge = max(0.0, min(40.0, base_edge + max(0, league_w) * 0.18 + max(0, market_w) * 0.22 + (score - 55) * 0.09))
        min_conf = float(state.get("min_confidence", 54))
        min_edge = float(state.get("min_edge", 0))
        if score < min_conf or edge < min_edge:
            debug["rejected"].append({"match": match, "reason": "threshold", "score": round(score,2), "edge": round(edge,2)})
            continue
        risk = risk_for(score, edge, odds)
        status = "AI STRONG" if score >= 75 else "AI VALUE" if score >= 64 else "AI WATCH"
        reason = (
            f"Self-learning score={score:.1f}; mode={state.get('mode')}; market={market}; "
            f"league_w={league_w:.1f}; market_w={market_w:.1f}; tempo={tempo:.1f}; pressure={pressure:.1f}"
        )
        ai_id = f"AI-{abs(hash((league, match, market, ts[:10]))) % 10_000_000:07d}"
        item = {
            "ai_id": ai_id,
            "created_at": ts,
            "source": first(row, ["_source"], "DATA_FEED"),
            "league": league,
            "match": match,
            "market": market,
            "odds": round(odds, 3),
            "confidence": round(score, 2),
            "edge": round(edge, 2),
            "ev": round(edge, 2),
            "ai_pick_score": round(score, 2),
            "risk": risk,
            "status": status,
            "tempo": round(tempo, 2),
            "pressure": round(pressure, 2),
            "momentum": round(momentum, 2),
            "model_reason": reason,
            "ai_generated": True,
        }
        rows.append(item)
        feature = {k: item.get(k, "") for k in FEATURE_COLUMNS if k in item}
        feature.update({"result": "PENDING", "profit": 0.0, "roi": 0.0})
        features.append(feature)

    out = pd.DataFrame(rows, columns=AI_COLUMNS)
    if not out.empty:
        out = out.sort_values(["ai_pick_score", "edge"], ascending=False).head(limit).reset_index(drop=True)
    debug["accepted"] = int(len(out))
    write_json(DEBUG_FILE, debug)
    append_feature_store(features)
    return out


def append_feature_store(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    new = pd.DataFrame(rows)
    if FEATURE_STORE_FILE.exists() and FEATURE_STORE_FILE.stat().st_size > 0:
        old = read_csv(FEATURE_STORE_FILE)
        combined = pd.concat([old, new], ignore_index=True, sort=False)
        if {"match", "market", "created_at"}.issubset(combined.columns):
            combined = combined.drop_duplicates(subset=["match", "market", "created_at"], keep="last")
    else:
        combined = new
    combined.to_csv(FEATURE_STORE_FILE, index=False)


def log_event(message: str, extra: Dict[str, Any] | None = None) -> None:
    row = {"created_at": now_iso(), "event": message}
    if extra:
        row.update(extra)
    df = pd.DataFrame([row])
    if EVENT_LOG_FILE.exists() and EVENT_LOG_FILE.stat().st_size > 0:
        old = read_csv(EVENT_LOG_FILE)
        df = pd.concat([old, df], ignore_index=True, sort=False)
    df.to_csv(EVENT_LOG_FILE, index=False)


def run_self_learning_cycle(limit: int = 12) -> Dict[str, Any]:
    state_before = load_state()
    picks = build_ai_picks(limit=limit)
    AI_PICKS_FILE.parent.mkdir(exist_ok=True)
    if picks.empty:
        pd.DataFrame(columns=AI_COLUMNS).to_csv(AI_PICKS_FILE, index=False)
    else:
        picks.to_csv(AI_PICKS_FILE, index=False)
    state_after = update_learning_state()
    result = {
        "status": "OK",
        "mode": state_after.get("mode"),
        "ai_picks": int(len(picks)),
        "cycles": int(state_after.get("cycles", 0)),
        "settled_samples": int(state_after.get("settled_samples", 0)),
        "file": str(AI_PICKS_FILE),
    }
    log_event("SELF_LEARNING_CYCLE", result)
    print(f"[AI-SELF-LEARNING] OK | picks={result['ai_picks']} | mode={result['mode']} | settled={result['settled_samples']}")
    return result


if __name__ == "__main__":
    run_self_learning_cycle()
