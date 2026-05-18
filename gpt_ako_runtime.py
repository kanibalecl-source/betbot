"""Runtime: read bot picks, evaluate with GPT web search, build AKO coupons."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from ako_coupon_builder import build_ako_coupons
from gpt_match_value_engine import MatchBetInput, evaluate_many

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PREMATCH_FILE = DATA_DIR / "auto_all_picks.csv"
LIVE_FILE = DATA_DIR / "live_matches.csv"
GPT_EVAL_FILE = DATA_DIR / "gpt_match_evaluations.csv"
GPT_COUPONS_FILE = DATA_DIR / "gpt_ako_coupons.json"
GPT_REPORT_FILE = DATA_DIR / "gpt_ako_report.md"


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        if path.exists() and path.stat().st_size > 0:
            return pd.read_csv(path)
    except Exception:
        pass
    return pd.DataFrame()


def _first(row: Any, names: List[str], default: Any = "") -> Any:
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
        return float(value)
    except Exception:
        return default


def load_candidates(limit: int = 20) -> List[MatchBetInput]:
    frames = []
    for path in [PREMATCH_FILE, LIVE_FILE]:
        df = _read_csv(path)
        if not df.empty:
            frames.append(df)
    if not frames:
        return []
    df = pd.concat(frames, ignore_index=True, sort=False)
    # Prefer the bot's best filtered picks as proposals; GPT decides independently whether they are worth playing.
    sort_cols = [c for c in ["ai_pick_score", "confidence", "ev", "edge"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, ascending=False)
    out: List[MatchBetInput] = []
    seen = set()
    for _, row in df.iterrows():
        match = str(_first(row, ["match", "mecz", "fixture"], "")).strip()
        if not match:
            home = str(_first(row, ["home_team", "home"], "")).strip()
            away = str(_first(row, ["away_team", "away"], "")).strip()
            match = f"{home} vs {away}" if home or away else ""
        market = str(_first(row, ["market", "typ", "signal"], "")).strip()
        odds = _num(_first(row, ["odds", "kurs_buk", "kurs"], 0), 0)
        key = (match.lower(), market.lower())
        if not match or not market or odds <= 1.0 or key in seen:
            continue
        seen.add(key)
        out.append(MatchBetInput(
            match=match,
            market=market,
            odds=odds,
            league=str(_first(row, ["league", "liga"], "")),
            country=str(_first(row, ["country"], "")),
            match_date=str(_first(row, ["match_date", "date", "commence_time"], "")),
            bookmaker=str(_first(row, ["bookmaker", "site"], "")),
            bot_confidence=_num(_first(row, ["confidence", "ai_pick_score"], 0), 0),
            bot_edge=_num(_first(row, ["edge"], 0), 0),
            bot_ev=_num(_first(row, ["ev"], 0), 0),
        ))
        if len(out) >= limit:
            break
    return out


def _write_report(coupons: Dict[str, Any], evaluations: List[Dict[str, Any]]) -> None:
    lines = ["# GPT AKO Report", "", f"Generated: {datetime.now(timezone.utc).isoformat()}", ""]
    lines.append("## Kupony AKO")
    if not coupons.get("coupons"):
        lines.append("Brak kuponu AKO spełniającego progi jakości. Lepiej grać single albo odpuścić.")
    for c in coupons.get("coupons", []):
        lines.append(f"### {c['coupon_name']} | kurs łączny: {c['total_odds']} | avg confidence: {c['avg_confidence']}%")
        for leg in c.get("legs", []):
            lines.append(f"- {leg['match']} | {leg['market']} @ {leg['odds']} | {leg['confidence']}% | {leg['risk']} — {leg['reason']}")
        lines.append("")
    lines.append("## Najlepsze single")
    for e in coupons.get("best_singles", [])[:10]:
        lines.append(f"- {e.get('match')} | {e.get('market')} @ {e.get('odds')} | {e.get('confidence')}% | value {e.get('value_rating')}/10 | {e.get('risk')}")
    lines.append("")
    lines.append("## Odrzucone / no-bet")
    for e in evaluations:
        if not e.get("play") or e.get("recommended_action") == "SKIP":
            lines.append(f"- {e.get('match')} | {e.get('market')} — {e.get('reason')}")
    GPT_REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


def run_gpt_ako_cycle(limit: int = 20) -> Dict[str, Any]:
    DATA_DIR.mkdir(exist_ok=True)
    candidates = load_candidates(limit=limit)
    evaluations = evaluate_many(candidates, limit=limit)
    pd.DataFrame(evaluations).to_csv(GPT_EVAL_FILE, index=False)
    coupons = build_ako_coupons(evaluations)
    GPT_COUPONS_FILE.write_text(json.dumps(coupons, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(coupons, evaluations)
    return {
        "status": "OK",
        "candidates": len(candidates),
        "evaluations": len(evaluations),
        "coupons": len(coupons.get("coupons", [])),
        "eval_file": str(GPT_EVAL_FILE),
        "coupons_file": str(GPT_COUPONS_FILE),
        "report_file": str(GPT_REPORT_FILE),
    }


if __name__ == "__main__":
    print(json.dumps(run_gpt_ako_cycle(), ensure_ascii=False, indent=2))
