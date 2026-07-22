"""Evidence-based recommendation gate derived from settled history.

Fail-open when no validated policy exists.  Once the diagnostic report marks
the policy as enforcement-ready, clearly negative segments and incomplete or
stale observations are rejected.  This module never changes probabilities.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from statistics import pstdev
from typing import Any, Mapping, Sequence

from storage_paths import get_data_dir


def _number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _odds_bucket(odds: float | None) -> str:
    if odds is None:
        return "MISSING"
    if odds < 1.50:
        return "1.01-1.49"
    if odds < 2.00:
        return "1.50-1.99"
    if odds < 2.50:
        return "2.00-2.49"
    if odds < 3.50:
        return "2.50-3.49"
    return "3.50+"


def load_policy(data_dir: str | Path | None = None) -> dict[str, Any]:
    configured = os.getenv("BETBOT_QUALITY_SELECTION_POLICY", "").strip()
    path = Path(configured) if configured else (
        Path(data_dir or get_data_dir()) / "quality_retraining" / "quality_selection_policy.json"
    )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return dict(payload) if isinstance(payload, Mapping) else {}
    except Exception:
        return {}


def evaluate_recommendation(
    observation: Mapping[str, Any],
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    policy = dict(policy or {})
    if not policy:
        return {
            "accepted": True,
            "status": "NO_VALIDATED_POLICY_FAIL_OPEN",
            "enforced": False,
            "reasons": ["selection_policy_missing"],
        }
    enforcement_requested = os.getenv(
        "BETBOT_QUALITY_SELECTION_GATE_ENFORCE", "true"
    ).strip().lower() in {"1", "true", "yes", "on"}
    enforced = bool(policy.get("enforcement_ready")) and enforcement_requested
    market = str(observation.get("market") or "UNKNOWN")
    league = str(observation.get("league") or "UNKNOWN")
    odds = _number(observation.get("odds"))
    edge = _number(observation.get("edge"))
    observed_at = _time(observation.get("odds_observed_at"))
    probabilities: Sequence[float] = tuple(
        value for key in (
            "current_probability", "xg_probability", "dixon_coles_probability"
        ) if (value := _number(observation.get(key))) is not None and 0.0 < value < 1.0
    )
    required = (
        observation.get("home_xg"), observation.get("away_xg"), odds,
        observation.get("current_probability"), market, league,
    )
    completeness = sum(value not in (None, "", "UNKNOWN") for value in required) / len(required)
    disagreement = pstdev(probabilities) if len(probabilities) > 1 else 0.0
    maximum_age = int(policy.get("maximum_odds_age_seconds", 300))
    age_seconds = None
    if observed_at is not None:
        age_seconds = max(0.0, (datetime.now(timezone.utc) - observed_at).total_seconds())
    segments = policy.get("segments", {})
    segments = segments if isinstance(segments, Mapping) else {}
    evidence = {
        "market_league": segments.get(f"market_league::{market}::{league}"),
        "market": segments.get(f"market::{market}"),
        "league": segments.get(f"league::{league}"),
        "odds_bucket": segments.get(f"odds_bucket::{_odds_bucket(odds)}"),
    }
    reasons: list[str] = []
    if completeness < float(policy.get("minimum_data_quality", 0.65)):
        reasons.append("insufficient_data_completeness")
    if observed_at is None:
        reasons.append("missing_odds_timestamp")
    elif age_seconds is not None and age_seconds > maximum_age:
        reasons.append("stale_odds")
    if disagreement > float(policy.get("maximum_model_disagreement", 0.15)):
        reasons.append("excessive_model_disagreement")
    if edge is None or edge < float(policy.get("base_minimum_edge", 0.02)):
        reasons.append("edge_below_quality_threshold")
    for field, segment in evidence.items():
        if isinstance(segment, Mapping) and segment.get("status") == "BLOCK":
            reasons.append(f"historically_negative_{field}_segment")
    hard_reasons = {
        "insufficient_data_completeness", "stale_odds",
        "excessive_model_disagreement", "edge_below_quality_threshold",
        "historically_negative_market_segment", "historically_negative_league_segment",
        "historically_negative_market_league_segment",
        "historically_negative_odds_bucket_segment",
    }
    rejected = enforced and any(reason in hard_reasons for reason in reasons)
    return {
        "accepted": not rejected,
        "status": "REJECT" if rejected else "ACCEPT" if not reasons else "REVIEW",
        "enforced": enforced,
        "reasons": reasons or ["quality_checks_passed"],
        "data_completeness": round(completeness, 4),
        "model_disagreement": round(disagreement, 6),
        "odds_age_seconds": round(age_seconds, 2) if age_seconds is not None else None,
        "segment_evidence": evidence,
        "probability_modified": False,
    }
