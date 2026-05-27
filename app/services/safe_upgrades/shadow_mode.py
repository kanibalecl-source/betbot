"""Passive shadow-mode upgrade layer for BetBot.

This module intentionally does NOT change live recommendations, staking,
probability, risk, API schemas, dashboard rendering, or existing data models.
It calculates additional diagnostics in parallel and writes them to a JSONL log
for later backtesting/validation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, UTC
import json
import os
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class ShadowAssessment:
    generated_at: str
    mode: str
    match_name: str
    market: str
    league: str | None
    current_recommendation: str
    current_probability: float
    current_edge: float
    current_confidence: float
    current_risk_level: str
    dynamic_confidence_signal: float
    league_profile_signal: float
    clv_intelligence_signal: float
    odds_anomaly_signal: float
    self_learning_signal: float
    combined_shadow_score: float
    shadow_comment: str


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _dynamic_confidence(edge: float, confidence: float, odds: float) -> float:
    # Passive diagnostic only: rewards agreement between edge and confidence,
    # penalizes very high odds because variance is higher.
    odds_penalty = max(0.0, odds - 3.5) * 4.0
    signal = confidence + (edge * 120.0) - odds_penalty
    return round(_clamp(signal, 0.0, 100.0), 2)


def _league_profile(league: str | None) -> float:
    # Neutral baseline. This is deliberately conservative until real league ROI
    # history is available. It must not whitelist/blacklist anything live.
    if not league:
        return 50.0
    return 55.0


def _clv_signal(raw: Mapping[str, Any], odds: float) -> float:
    opening = _num(raw.get("opening_odds") or raw.get("open_odds"), odds)
    current = odds
    if opening <= 1.0 or current <= 1.0:
        return 50.0
    # Positive when current odds are shorter than opening odds.
    movement = (opening - current) / opening
    return round(_clamp(50.0 + movement * 250.0, 0.0, 100.0), 2)


def _odds_anomaly(raw: Mapping[str, Any], odds: float) -> float:
    # 100 means no visible anomaly. Passive only.
    volatility = _num(raw.get("odds_volatility") or raw.get("volatility"), 0.0)
    if volatility <= 0:
        return 75.0
    return round(_clamp(100.0 - volatility * 100.0, 0.0, 100.0), 2)


def _self_learning_signal(raw: Mapping[str, Any]) -> float:
    # Neutral placeholder until settled-bet history/backtest is connected.
    roi = _num(raw.get("historical_roi"), 0.0)
    sample = _num(raw.get("historical_sample_size"), 0.0)
    if sample < 50:
        return 50.0
    return round(_clamp(50.0 + roi * 100.0, 0.0, 100.0), 2)


def assess_shadow(raw: Mapping[str, Any], current_output: Mapping[str, Any]) -> ShadowAssessment:
    match_name = str(current_output.get("match_name", "UNKNOWN"))
    market = str(current_output.get("market", "UNKNOWN"))
    league = raw.get("league")
    if league is not None:
        league = str(league)

    probability = _num(current_output.get("probability"), 0.5)
    edge = _num(current_output.get("edge"), 0.0)
    confidence = _num(current_output.get("confidence"), probability * 100.0)
    odds = _num(current_output.get("bookmaker_odds"), raw.get("odds") or raw.get("kurs_buk") or 2.0)

    dynamic = _dynamic_confidence(edge=edge, confidence=confidence, odds=odds)
    league_signal = _league_profile(league)
    clv = _clv_signal(raw, odds)
    anomaly = _odds_anomaly(raw, odds)
    learning = _self_learning_signal(raw)

    combined = round(
        dynamic * 0.35
        + league_signal * 0.15
        + clv * 0.20
        + anomaly * 0.15
        + learning * 0.15,
        2,
    )

    if combined >= 70:
        comment = "shadow_positive"
    elif combined >= 50:
        comment = "shadow_neutral"
    else:
        comment = "shadow_caution"

    return ShadowAssessment(
        generated_at=datetime.now(UTC).isoformat(),
        mode="shadow_only_no_runtime_effect",
        match_name=match_name,
        market=market,
        league=league,
        current_recommendation=str(current_output.get("recommendation", "UNKNOWN")),
        current_probability=round(probability, 4),
        current_edge=round(edge, 4),
        current_confidence=round(confidence, 2),
        current_risk_level=str(current_output.get("risk_level", "UNKNOWN")),
        dynamic_confidence_signal=dynamic,
        league_profile_signal=league_signal,
        clv_intelligence_signal=clv,
        odds_anomaly_signal=anomaly,
        self_learning_signal=learning,
        combined_shadow_score=combined,
        shadow_comment=comment,
    )


def write_shadow_event(assessment: ShadowAssessment, path: str | None = None) -> None:
    target = Path(path or os.getenv("BETBOT_SHADOW_LOG", "data/shadow_upgrade_events.jsonl"))
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(assessment), ensure_ascii=False, sort_keys=True) + "\n")


def run_shadow_mode(raw: Mapping[str, Any], current_output: Mapping[str, Any]) -> None:
    """Run passive diagnostics.

    Any error is swallowed by the caller. This function must never affect the
    live prediction response.
    """
    assessment = assess_shadow(raw=raw, current_output=current_output)
    write_shadow_event(assessment)
