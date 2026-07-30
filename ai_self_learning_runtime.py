"""Full self-learning runtime for KANIBAL ANALYTICS.

This module runs in the background scheduler and closes the loop:
AI picks -> settlement/history -> feature store -> adaptive model state -> new AI picks.
It does not place bets and it does not connect to bookmaker accounts.
"""
from __future__ import annotations

import json
import os
import hashlib
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd
from storage_paths import get_data_dir

try:
    from betbot.storage.append_only_history import append_event, append_records
except Exception:
    def append_event(*args, **kwargs):
        return None
    def append_records(*args, **kwargs):
        return 0

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(get_data_dir()).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

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

AI_MODE_SETTINGS = {
    "main": {
        "prematch_file": "auto_all_picks.csv",
        "ai_file": "ai_picks.csv",
        "model_dir": "ai_learning",
        "label": "AI",
        "append_stream": "ai_picks",
    },
}

AI_COLUMNS = [
    "ai_id", "observation_key", "created_at", "source", "ai_mode", "ai_label",
    "pick_id", "fixture_id", "odds_event_id", "match_date",
    "league", "match", "market", "odds", "kurs_buk", "kurs_model", "kurs_bota",
    "prawd_model", "prawd_final", "bookmaker", "bookmaker_id",
    "bookmaker_scope", "bookmaker_verified", "market_scope", "odds_observed_at",
    "market_integrity_schema", "market_integrity_status",
    "market_consensus_id", "market_bookmaker_count",
    "quality_gate_status", "quality_gate_enforced", "quality_data_completeness",
    "confidence", "edge", "ev", "ai_pick_score", "risk", "status",
    "closing_odds", "clv_percent", "home_xg", "away_xg",
    "advanced_total_xg", "advanced_over25_prob", "advanced_under25_prob",
    "advanced_market_prob", "advanced_probability_method",
    "advanced_probability_version", "advanced_probability_integrity", "marza_%",
    "tempo", "pressure", "momentum", "momentum_score", "momentum_label",
    "sharp_score", "sharp_label", "sharp_signals",
    "meta_probability", "meta_weight_model", "meta_weight_market",
    "meta_weight_xg", "meta_weight_momentum", "meta_weight_sharp",
    "kelly_10", "stage_kelly_fraction", "dynamic_stake",
    "model_reason", "ai_generated"
]

FEATURE_COLUMNS = [
    "ai_id", "observation_key", "created_at", "fixture_id", "pick_id",
    "league", "match", "market", "odds", "odds_observed_at",
    "market_consensus_id", "confidence", "edge", "ev", "tempo", "pressure",
    "momentum", "risk", "source", "result", "profit", "roi"
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
    "min_edge": 2.0,
    "league_weights": {},
    "market_weights": {},
    "risk_weights": {"LOW": 4.0, "MEDIUM": 1.5, "HIGH": -3.0},
    "last_summary": {},
}

MARKETS = {
    "HOME_WIN", "DRAW", "AWAY_WIN",
    "OVER_0.5", "UNDER_0.5", "OVER_1.5", "UNDER_1.5",
    "OVER_2.5", "UNDER_2.5", "OVER_3.5", "UNDER_3.5",
    "OVER_4.5", "UNDER_4.5", "BTTS_YES", "BTTS_NO",
}

REJECTION_DESCRIPTIONS = {
    "no_match_name": "Brak nazwy meczu.",
    "missing_fixture_id": "Brak identyfikatora wydarzenia.",
    "missing_pick_id": "Brak identyfikatora typu.",
    "unsupported_or_missing_market": "Brak rynku lub rynek nieobsługiwany.",
    "missing_bookmaker_odds": "Brak prawidłowego kursu bukmachera.",
    "missing_model_odds": "Brak prawidłowego kursu modelu.",
    "missing_bot_odds": "Brak prawidłowego kursu bota.",
    "missing_confidence": "Brak prawidłowej wartości pewności.",
    "missing_edge": "Brak wyliczonej przewagi.",
    "missing_ev": "Brak wyliczonej wartości oczekiwanej.",
    "missing_odds_timestamp": "Brak czasu pobrania kursu.",
    "stale_odds": "Kurs jest starszy niż dopuszczalny limit.",
    "unverified_bookmaker": "Bukmacher nie został zweryfikowany.",
    "invalid_bookmaker_scope": "Bukmacher nie należy do polskiej listy dozwolonej.",
    "invalid_market_scope": "Rynek nie dotyczy pełnego czasu meczu.",
    "market_integrity_not_passed": "Kontrola integralności rynku nie zakończyła się PASS.",
    "missing_market_consensus": "Brak identyfikatora konsensusu rynku.",
    "insufficient_bookmaker_consensus": "Konsensus pochodzi z mniej niż dwóch źródeł.",
    "quality_gate_not_passed": "Rekord nie przeszedł bramki jakości.",
    "threshold": "Wynik AI lub przewaga są niższe od aktywnego progu.",
    "better_market_same_fixture": "Wybrano lepszy prawidłowy rynek dla tego meczu.",
    "output_limit": "Rekord nie zmieścił się w limicie publikacji.",
}


def configure_ai_mode(mode: str = "main") -> Dict[str, Any]:
    global PREMATCH_FILE, AI_PICKS_FILE, AI_MODEL_DIR, MODEL_STATE_FILE, FEATURE_STORE_FILE, EVENT_LOG_FILE, DEBUG_FILE
    mode = str(mode or "main").lower()
    if mode not in AI_MODE_SETTINGS:
        mode = "main"
    settings = dict(AI_MODE_SETTINGS[mode])
    settings["mode"] = mode
    PREMATCH_FILE = DATA_DIR / settings["prematch_file"]
    AI_PICKS_FILE = DATA_DIR / settings["ai_file"]
    AI_MODEL_DIR = DATA_DIR / settings["model_dir"]
    AI_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_STATE_FILE = AI_MODEL_DIR / "ai_model_state.json"
    FEATURE_STORE_FILE = AI_MODEL_DIR / "ai_feature_store.csv"
    EVENT_LOG_FILE = AI_MODEL_DIR / "ai_learning_events.csv"
    DEBUG_FILE = DATA_DIR / f"ai_runtime_debug_{mode}.json"
    return settings


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


def optional_num(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def percent_value(value: Any) -> float | None:
    number = optional_num(value)
    if number is None:
        return None
    return number * 100.0 if abs(number) <= 1.0 else number


def stable_observation_key(row: Any, market: str) -> str:
    payload = "|".join(
        str(first(row, [name], "")).strip()
        for name in (
            "fixture_id", "pick_id", "odds_event_id", "odds_observed_at",
            "market_consensus_id",
        )
    )
    payload = f"{payload}|{market}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_candidate(row: Any) -> tuple[bool, str, Dict[str, Any]]:
    fixture_id = str(first(row, ["fixture_id"], "")).strip()
    pick_id = str(first(row, ["pick_id"], "")).strip()
    market = normalize_market(first(row, ["market", "typ"], ""))
    bookmaker_odds = optional_num(
        first(row, ["kurs_buk", "bookmaker_odds", "odds"], None)
    )
    model_odds = optional_num(first(row, ["kurs_model", "model_odds"], None))
    bot_odds = optional_num(first(row, ["kurs_bota", "bot_odds", "fair_odds"], None))
    confidence = percent_value(
        first(row, ["confidence", "advanced_confidence"], None)
    )
    edge_percent = percent_value(first(row, ["edge"], None))
    ev_percent = percent_value(first(row, ["ev"], None))
    observed_at_raw = first(row, ["odds_observed_at"], "")
    observed_at = parse_time(observed_at_raw)
    maximum_age = max(
        60,
        int(
            os.getenv(
                "BETBOT_AI_MAX_ODDS_AGE_SECONDS",
                os.getenv("BETBOT_MAX_ODDS_AGE_SECONDS", "600"),
            )
        ),
    )
    age_seconds = (
        max(0.0, (datetime.now(timezone.utc) - observed_at).total_seconds())
        if observed_at is not None
        else None
    )
    bookmaker_verified = truthy(first(row, ["bookmaker_verified"], False))
    bookmaker_scope = str(first(row, ["bookmaker_scope"], "")).strip()
    market_scope = str(first(row, ["market_scope"], "")).strip()
    integrity_status = str(first(row, ["market_integrity_status"], "")).strip().upper()
    consensus_id = str(first(row, ["market_consensus_id"], "")).strip()
    bookmaker_count = optional_num(first(row, ["market_bookmaker_count"], None))
    quality_status = str(first(row, ["quality_gate_status"], "")).strip().upper()
    quality_enforced = truthy(first(row, ["quality_gate_enforced"], False))

    checks = (
        (bool(fixture_id), "missing_fixture_id"),
        (bool(pick_id), "missing_pick_id"),
        (market in MARKETS, "unsupported_or_missing_market"),
        (bookmaker_odds is not None and bookmaker_odds > 1.0, "missing_bookmaker_odds"),
        (model_odds is not None and model_odds > 1.0, "missing_model_odds"),
        (bot_odds is not None and bot_odds > 1.0, "missing_bot_odds"),
        (confidence is not None and 0.0 < confidence < 100.0, "missing_confidence"),
        (edge_percent is not None, "missing_edge"),
        (ev_percent is not None, "missing_ev"),
        (observed_at is not None, "missing_odds_timestamp"),
        (
            age_seconds is not None and age_seconds <= maximum_age,
            "stale_odds",
        ),
        (bookmaker_verified, "unverified_bookmaker"),
        (bookmaker_scope == "POLAND_ALLOWLIST", "invalid_bookmaker_scope"),
        (market_scope == "FULL_MATCH", "invalid_market_scope"),
        (integrity_status == "PASS", "market_integrity_not_passed"),
        (bool(consensus_id), "missing_market_consensus"),
        (
            bookmaker_count is not None and bookmaker_count >= 2,
            "insufficient_bookmaker_consensus",
        ),
        (
            quality_enforced and quality_status in {"ACCEPT", "REVIEW"},
            "quality_gate_not_passed",
        ),
    )
    for passed, reason in checks:
        if not passed:
            return False, reason, {}
    return True, "accepted", {
        "fixture_id": fixture_id,
        "pick_id": pick_id,
        "market": market,
        "bookmaker_odds": bookmaker_odds,
        "model_odds": model_odds,
        "bot_odds": bot_odds,
        "confidence": confidence,
        "edge_percent": edge_percent,
        "ev_percent": ev_percent,
        "odds_observed_at": str(observed_at_raw),
        "age_seconds": age_seconds,
        "bookmaker_count": int(bookmaker_count),
        "consensus_id": consensus_id,
        "quality_status": quality_status,
    }


def rejection_record(
    row: Any,
    *,
    idx: int,
    match: str,
    reason: str,
    phase: str,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Return a safe, non-secret diagnostic record for one rejected candidate."""
    observed_at_raw = first(row, ["odds_observed_at"], "")
    observed_at = parse_time(observed_at_raw)
    age_seconds = (
        max(0.0, (datetime.now(timezone.utc) - observed_at).total_seconds())
        if observed_at is not None
        else None
    )
    record: Dict[str, Any] = {
        "idx": int(idx),
        "fixture_id": str(first(row, ["fixture_id"], "")).strip(),
        "pick_id": str(first(row, ["pick_id"], "")).strip(),
        "match": str(match or "").strip(),
        "market": normalize_market(first(row, ["market", "typ"], "")),
        "phase": phase,
        "reason": reason,
        "description": REJECTION_DESCRIPTIONS.get(reason, reason),
        "bookmaker": str(
            first(row, ["bookmaker", "margin_bookmaker"], "")
        ).strip(),
        "bookmaker_verified": truthy(
            first(row, ["bookmaker_verified"], False)
        ),
        "bookmaker_scope": str(first(row, ["bookmaker_scope"], "")).strip(),
        "market_scope": str(first(row, ["market_scope"], "")).strip(),
        "market_integrity_status": str(
            first(row, ["market_integrity_status"], "")
        ).strip().upper(),
        "market_consensus_id": str(
            first(row, ["market_consensus_id"], "")
        ).strip(),
        "market_bookmaker_count": optional_num(
            first(row, ["market_bookmaker_count"], None)
        ),
        "quality_gate_status": str(
            first(row, ["quality_gate_status"], "")
        ).strip().upper(),
        "quality_gate_enforced": truthy(
            first(row, ["quality_gate_enforced"], False)
        ),
        "odds_observed_at": str(observed_at_raw),
        "odds_age_seconds": round(age_seconds, 3)
        if age_seconds is not None
        else None,
        "bookmaker_odds": optional_num(
            first(row, ["kurs_buk", "bookmaker_odds", "odds"], None)
        ),
        "model_odds": optional_num(
            first(row, ["kurs_model", "model_odds"], None)
        ),
        "bot_odds": optional_num(
            first(row, ["kurs_bota", "bot_odds", "fair_odds"], None)
        ),
    }
    if extra:
        record.update(extra)
    return record


def summarize_gate_report(debug: Dict[str, Any]) -> Dict[str, Any]:
    rejected = list(debug.get("rejected", []) or [])
    reasons = Counter(str(item.get("reason", "unknown")) for item in rejected)
    phases = Counter(str(item.get("phase", "unknown")) for item in rejected)
    return {
        "schema_version": "betbot.ai_gate_report.v14.1",
        "updated_at": debug.get("updated_at", now_iso()),
        "ai_mode": debug.get("ai_mode", "main"),
        "learning_mode": debug.get("mode", "UNKNOWN"),
        "candidates": int(debug.get("candidates", 0) or 0),
        "accepted": int(debug.get("accepted", 0) or 0),
        "rejected": len(rejected),
        "rejection_reasons": dict(sorted(reasons.items())),
        "rejection_phases": dict(sorted(phases.items())),
        "min_confidence": debug.get("min_confidence"),
        "min_edge": debug.get("min_edge"),
        "fail_closed": True,
    }


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
    if s in {"win", "won", "wygrana", "trafiony", "true", "1"}:
        return 1.0
    if s in {"loss", "lose", "lost", "przegrana", "nietrafiony", "false", "0"}:
        return -1.0
    if s in {"push", "void", "zwrot"}:
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

    minimum_segment = max(
        20, int(os.getenv("BETBOT_AI_LEARNING_MIN_SEGMENT_SAMPLES", "50"))
    )
    prior_strength = max(
        20.0, float(os.getenv("BETBOT_AI_LEARNING_PRIOR_STRENGTH", "100"))
    )

    def raw_group_weight(g: pd.DataFrame) -> float:
        n = len(g)
        rs = pd.to_numeric(g.get("result_score", pd.Series([0]*n)), errors="coerce").fillna(0).mean()
        profit = pd.to_numeric(g.get("profit", pd.Series([0]*n)), errors="coerce").fillna(0).mean()
        roi = pd.to_numeric(g.get("roi", pd.Series([0]*n)), errors="coerce").fillna(0).mean()
        return max(-18.0, min(22.0, rs * 12.0 + profit * 1.5 + roi * 0.18))

    global_weight = raw_group_weight(df)

    def group_weight(g: pd.DataFrame) -> float | None:
        n = len(g)
        if n < minimum_segment:
            return None
        raw = raw_group_weight(g)
        shrunk = (n * raw + prior_strength * global_weight) / (n + prior_strength)
        return round(max(-18.0, min(22.0, shrunk)), 3)

    if "league" in df.columns:
        for league, g in df.groupby(df["league"].astype(str)):
            if league and league != "nan":
                weight = group_weight(g)
                if weight is not None:
                    league_weights[league] = weight
    if "market" in df.columns:
        df["market_norm"] = df["market"].apply(normalize_market)
        for market, g in df.groupby("market_norm"):
            if market and market != "nan":
                weight = group_weight(g)
                if weight is not None:
                    market_weights[market] = weight
    summary.update({
        "leagues": len(league_weights),
        "markets": len(market_weights),
        "minimum_segment_samples": minimum_segment,
        "prior_strength": prior_strength,
    })
    return league_weights, market_weights, summary


def _quality_gate() -> Dict[str, Any]:
    work = Path(get_data_dir()).resolve() / "quality_retraining"
    try:
        guardian = json.loads((work / "data_quality_guardian.json").read_text(encoding="utf-8"))
    except Exception:
        guardian = {}
    try:
        scorecard = json.loads(
            (work / "statistical_evidence_scorecard_v8.json").read_text(encoding="utf-8")
        )
    except Exception:
        scorecard = {}
    readiness = guardian.get("training_readiness", {}) or {}
    return {
        "guardian_healthy": guardian.get("status") == "HEALTHY",
        "training_ready": readiness.get("ready_for_validation") is True,
        "statistical_edge_confirmed": scorecard.get("confirmed_statistical_edge") is True,
        "scorecard_status": scorecard.get("status", "MISSING"),
    }


def update_learning_state() -> Dict[str, Any]:
    state = load_state()
    results = combine_results()
    gate = _quality_gate()
    permitted = gate["guardian_healthy"] and gate["training_ready"]
    if permitted:
        league_weights, market_weights, summary = compute_weights(results)
    else:
        league_weights, market_weights = {}, {}
        summary = {"rows": int(len(results)), "leagues": 0, "markets": 0}
    state["cycles"] = int(state.get("cycles", 0)) + 1
    state["samples"] = int(len(read_csv(FEATURE_STORE_FILE))) if FEATURE_STORE_FILE.exists() else 0
    state["settled_samples"] = int(len(results))
    state["league_weights"] = league_weights
    state["market_weights"] = market_weights
    state["learning_gate"] = gate
    # No adaptive production weights are applied before authoritative data
    # quality gates pass. Thresholds tighten only with independent evidence.
    if len(results) < 300 or not permitted:
        state["mode"] = "COLLECTING_QUALITY_DATA"
        state["min_confidence"] = 54.0
        state["min_edge"] = 2.0
    elif not gate["statistical_edge_confirmed"]:
        state["mode"] = "VALIDATED_SHADOW_LEARNING"
        state["min_confidence"] = 60.0
        state["min_edge"] = 1.5
    else:
        state["mode"] = "PRODUCTION"
        state["min_confidence"] = 66.0
        state["min_edge"] = 2.0
    state["last_summary"] = summary
    save_state(state)
    return state


def candidates(label: str = "AI") -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    live = read_csv(LIVE_FILE)
    if not live.empty:
        live = live.copy()
        live["_source"] = "LIVE_FEED"
        frames.append(live)
    pre = read_csv(PREMATCH_FILE)
    if not pre.empty:
        pre = pre.copy()
        pre["_source"] = f"{label}_FIXTURE_UNIVERSE"
        frames.append(pre)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def risk_for(score: float, edge: float, odds: float) -> str:
    if score >= 78 and edge >= 5 and odds <= 2.35:
        return "LOW"
    if score >= 63 and edge >= 1:
        return "MEDIUM"
    return "HIGH"


def build_ai_picks(limit: int = 12, mode: str = "main") -> pd.DataFrame:
    settings = configure_ai_mode(mode)
    state = update_learning_state()
    cand = candidates(settings["label"])
    debug: Dict[str, Any] = {
        "updated_at": now_iso(),
        "ai_mode": settings["mode"],
        "source_file": str(PREMATCH_FILE),
        "output_file": str(AI_PICKS_FILE),
        "mode": state.get("mode"),
        "candidates": int(len(cand)),
        "accepted": 0,
        "rejected": [],
        "min_confidence": state.get("min_confidence"),
        "min_edge": state.get("min_edge"),
    }
    if cand.empty:
        debug["gate_report"] = summarize_gate_report(debug)
        write_json(DEBUG_FILE, debug)
        return pd.DataFrame(columns=AI_COLUMNS)

    league_weights = state.get("league_weights", {}) or {}
    market_weights = state.get("market_weights", {}) or {}
    rows: List[Dict[str, Any]] = []
    qualified_meta: Dict[str, Dict[str, Any]] = {}
    features: List[Dict[str, Any]] = []
    ts = now_iso()
    for idx, row in cand.iterrows():
        league = str(first(row, ["league", "liga"], "-")).strip()
        match = str(first(row, ["match", "mecz", "fixture"], "")).strip()
        if not match:
            home = str(first(row, ["home", "home_team"], "")).strip()
            away = str(first(row, ["away", "away_team"], "")).strip()
            match = f"{home} vs {away}" if home or away else ""
        if not match:
            debug["rejected"].append(
                rejection_record(
                    row,
                    idx=int(idx),
                    match="",
                    reason="no_match_name",
                    phase="identity",
                )
            )
            continue
        valid, rejection_reason, verified = validate_candidate(row)
        if not valid:
            debug["rejected"].append(
                rejection_record(
                    row,
                    idx=int(idx),
                    match=match,
                    reason=rejection_reason,
                    phase="validation",
                )
            )
            continue

        base_conf = float(verified["confidence"])
        base_edge = float(verified["edge_percent"])
        base_ev = float(verified["ev_percent"])
        odds = float(verified["bookmaker_odds"])
        tempo_value = optional_num(first(row, ["tempo", "tempo_score"], None))
        pressure_value = optional_num(first(row, ["pressure"], None))
        momentum_value = optional_num(first(row, ["momentum"], None))
        tempo = tempo_value if tempo_value is not None else 0.0
        pressure = pressure_value if pressure_value is not None else 0.0
        momentum = momentum_value if momentum_value is not None else 0.0
        league_w = float(league_weights.get(league, 0.0))
        market = str(verified["market"])
        market_w = float(market_weights.get(market, 0.0))
        score = max(
            0.0,
            min(
                100.0,
                (base_conf * 0.60)
                + (min(max(base_edge, 0.0), 15.0) / 15.0 * 20.0)
                + (min(max(base_ev, 0.0), 25.0) / 25.0 * 20.0)
                + league_w
                + market_w,
            ),
        )
        edge = base_edge
        min_conf = float(state.get("min_confidence", 54))
        source_required_edge = percent_value(
            first(row, ["quality_required_edge"], None)
        )
        min_edge = max(
            float(state.get("min_edge", 2.0)),
            source_required_edge if source_required_edge is not None else 2.0,
        )
        if score < min_conf or edge < min_edge:
            debug["rejected"].append(
                rejection_record(
                    row,
                    idx=int(idx),
                    match=match,
                    reason="threshold",
                    phase="selection",
                    extra={
                        "score": round(score, 2),
                        "required_score": round(min_conf, 2),
                        "edge": round(edge, 2),
                        "required_edge": round(min_edge, 2),
                    },
                )
            )
            continue
        risk = risk_for(score, edge, odds)
        status = "AI STRONG" if score >= 75 else "AI VALUE" if score >= 64 else "AI WATCH"
        reason = (
            f"Self-learning score={score:.1f}; mode={state.get('mode')}; market={market}; "
            f"league_w={league_w:.1f}; market_w={market_w:.1f}; tempo={tempo:.1f}; pressure={pressure:.1f}"
        )
        observation_key = stable_observation_key(row, market)
        ai_id = f"AI-{observation_key[:16].upper()}"
        item = {
            "ai_id": ai_id,
            "observation_key": observation_key,
            "created_at": ts,
            "source": first(row, ["_source"], "DATA_FEED"),
            "ai_mode": settings["mode"],
            "ai_label": settings["label"],
            "pick_id": verified["pick_id"],
            "fixture_id": verified["fixture_id"],
            "odds_event_id": first(row, ["odds_event_id"], ""),
            "match_date": first(row, ["match_date"], ""),
            "league": league,
            "match": match,
            "market": market,
            "odds": round(odds, 3),
            "kurs_buk": round(odds, 3),
            "kurs_model": round(float(verified["model_odds"]), 4),
            "kurs_bota": round(float(verified["bot_odds"]), 4),
            "prawd_model": first(row, ["prawd_model", "model_probability"], ""),
            "prawd_final": first(row, ["prawd_final", "final_probability"], ""),
            "bookmaker": first(row, ["bookmaker", "margin_bookmaker"], ""),
            "bookmaker_id": first(row, ["bookmaker_id"], ""),
            "bookmaker_scope": first(row, ["bookmaker_scope"], ""),
            "bookmaker_verified": True,
            "market_scope": first(row, ["market_scope"], ""),
            "odds_observed_at": verified["odds_observed_at"],
            "market_integrity_schema": first(row, ["market_integrity_schema"], ""),
            "market_integrity_status": first(row, ["market_integrity_status"], ""),
            "market_consensus_id": verified["consensus_id"],
            "market_bookmaker_count": verified["bookmaker_count"],
            "quality_gate_status": verified["quality_status"],
            "quality_gate_enforced": True,
            "quality_data_completeness": first(
                row, ["quality_data_completeness"], ""
            ),
            "confidence": round(score, 2),
            "edge": round(base_edge / 100.0, 6),
            "ev": round(base_ev / 100.0, 6),
            "ai_pick_score": round(score, 2),
            "risk": risk,
            "status": status,
            "closing_odds": first(row, ["closing_odds"], ""),
            "clv_percent": first(row, ["clv_percent"], ""),
            "home_xg": first(row, ["home_xg"], ""),
            "away_xg": first(row, ["away_xg"], ""),
            "advanced_total_xg": first(row, ["advanced_total_xg"], ""),
            "advanced_over25_prob": first(row, ["advanced_over25_prob"], ""),
            "advanced_under25_prob": first(row, ["advanced_under25_prob"], ""),
            "advanced_market_prob": first(row, ["advanced_market_prob"], ""),
            "advanced_probability_method": first(
                row, ["advanced_probability_method"], ""
            ),
            "advanced_probability_version": first(
                row, ["advanced_probability_version"], ""
            ),
            "advanced_probability_integrity": first(
                row, ["advanced_probability_integrity"], ""
            ),
            "marza_%": first(row, ["marza_%"], ""),
            "tempo": round(tempo, 2),
            "pressure": round(pressure, 2),
            "momentum": round(momentum, 2),
            "momentum_score": first(row, ["momentum_score"], ""),
            "momentum_label": first(row, ["momentum_label"], ""),
            "sharp_score": first(row, ["sharp_score"], ""),
            "sharp_label": first(row, ["sharp_label"], ""),
            "sharp_signals": first(row, ["sharp_signals"], ""),
            "meta_probability": first(row, ["meta_probability"], ""),
            "meta_weight_model": first(row, ["meta_weight_model"], ""),
            "meta_weight_market": first(row, ["meta_weight_market"], ""),
            "meta_weight_xg": first(row, ["meta_weight_xg"], ""),
            "meta_weight_momentum": first(row, ["meta_weight_momentum"], ""),
            "meta_weight_sharp": first(row, ["meta_weight_sharp"], ""),
            "kelly_10": first(row, ["kelly_10"], ""),
            "stage_kelly_fraction": first(row, ["stage_kelly_fraction"], ""),
            "dynamic_stake": first(row, ["dynamic_stake"], ""),
            "model_reason": reason,
            "ai_generated": True,
        }
        rows.append(item)
        qualified_meta[observation_key] = {
            "idx": int(idx),
            "row": row,
            "match": match,
            "fixture_id": verified["fixture_id"],
        }

    out = pd.DataFrame(rows, columns=AI_COLUMNS)
    if not out.empty:
        qualified = out.sort_values(
            ["ai_pick_score", "edge", "ev"],
            ascending=False,
        )
        out = (
            qualified
            .drop_duplicates(subset=["fixture_id"], keep="first")
            .head(limit)
            .reset_index(drop=True)
        )
        selected_keys = set(out["observation_key"].astype(str))
        selected_fixtures = set(out["fixture_id"].astype(str))
        for candidate in qualified.to_dict("records"):
            observation_key = str(candidate.get("observation_key", ""))
            if observation_key in selected_keys:
                continue
            meta = qualified_meta.get(observation_key, {})
            reason = (
                "better_market_same_fixture"
                if str(candidate.get("fixture_id", "")) in selected_fixtures
                else "output_limit"
            )
            debug["rejected"].append(
                rejection_record(
                    meta.get("row", {}),
                    idx=int(meta.get("idx", -1)),
                    match=str(meta.get("match", candidate.get("match", ""))),
                    reason=reason,
                    phase="ranking",
                    extra={
                        "ai_pick_score": candidate.get("ai_pick_score"),
                        "observation_key": observation_key,
                    },
                )
            )
        for item in out.to_dict("records"):
            feature = {key: item.get(key, "") for key in FEATURE_COLUMNS}
            feature.update({"result": "PENDING", "profit": 0.0, "roi": 0.0})
            features.append(feature)
    debug["accepted"] = int(len(out))
    debug["gate_report"] = summarize_gate_report(debug)
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
        if "observation_key" in combined.columns:
            combined = combined.drop_duplicates(
                subset=["observation_key"], keep="last"
            )
        elif {"match", "market", "created_at"}.issubset(combined.columns):
            combined = combined.drop_duplicates(
                subset=["match", "market", "created_at"], keep="last"
            )
    else:
        combined = new
    combined.to_csv(FEATURE_STORE_FILE, index=False)
    append_records("learning_feature_store", rows, source="ai_self_learning_runtime.py")


def log_event(message: str, extra: Dict[str, Any] | None = None) -> None:
    row = {"created_at": now_iso(), "event": message}
    if extra:
        row.update(extra)
    df = pd.DataFrame([row])
    if EVENT_LOG_FILE.exists() and EVENT_LOG_FILE.stat().st_size > 0:
        old = read_csv(EVENT_LOG_FILE)
        df = pd.concat([old, df], ignore_index=True, sort=False)
    df.to_csv(EVENT_LOG_FILE, index=False)
    append_event("learning_events", row, source="ai_self_learning_runtime.py")


def run_self_learning_cycle(limit: int = 12, mode: str = "main") -> Dict[str, Any]:
    settings = configure_ai_mode(mode)
    state_before = load_state()
    picks = build_ai_picks(limit=limit, mode=mode)
    AI_PICKS_FILE.parent.mkdir(exist_ok=True)
    if picks.empty:
        pd.DataFrame(columns=AI_COLUMNS).to_csv(AI_PICKS_FILE, index=False)
    else:
        picks.to_csv(AI_PICKS_FILE, index=False)
        append_records(settings["append_stream"], picks.to_dict("records"), source="ai_self_learning_runtime.py")
    state_after = update_learning_state()
    try:
        debug = json.loads(DEBUG_FILE.read_text(encoding="utf-8"))
    except Exception:
        debug = {}
    gate_report = debug.get("gate_report") or summarize_gate_report(debug)
    result = {
        "status": "OK",
        "ai_mode": settings["mode"],
        "ai_label": settings["label"],
        "mode": state_after.get("mode"),
        "ai_picks": int(len(picks)),
        "cycles": int(state_after.get("cycles", 0)),
        "settled_samples": int(state_after.get("settled_samples", 0)),
        "file": str(AI_PICKS_FILE),
        "candidate_count": int(gate_report.get("candidates", 0)),
        "rejected_count": int(gate_report.get("rejected", 0)),
        "rejection_reasons": gate_report.get("rejection_reasons", {}),
        "gate_report_file": str(DEBUG_FILE),
    }
    log_event("SELF_LEARNING_CYCLE", result)
    print(f"[AI-SELF-LEARNING] {settings['label']} OK | picks={result['ai_picks']} | mode={result['mode']} | settled={result['settled_samples']}")
    print(
        "[AI-SELF-LEARNING] GATE REPORT | "
        + json.dumps(gate_report, ensure_ascii=False, sort_keys=True)
    )
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=sorted(AI_MODE_SETTINGS), default="main")
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()
    run_self_learning_cycle(limit=args.limit, mode=args.mode)
