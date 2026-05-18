"""Build AKO coupons from GPT match evaluations."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


@dataclass
class CouponConfig:
    name: str
    min_confidence: float
    max_risk: str
    legs: int
    min_value_rating: float


RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "NO_BET": 3}
DEFAULT_CONFIGS = [
    CouponConfig("SAFE_AKO", min_confidence=72, max_risk="LOW", legs=2, min_value_rating=6.5),
    CouponConfig("BALANCED_AKO", min_confidence=66, max_risk="MEDIUM", legs=3, min_value_rating=6.0),
    CouponConfig("AGGRESSIVE_AKO", min_confidence=60, max_risk="HIGH", legs=4, min_value_rating=5.5),
]


def _score(e: Dict[str, Any]) -> float:
    conf = float(e.get("confidence") or 0)
    val = float(e.get("value_rating") or 0) * 10
    odds = float(e.get("odds") or 1)
    risk_penalty = RISK_ORDER.get(str(e.get("risk", "NO_BET")), 3) * 8
    return conf * 0.55 + val * 0.35 + min(odds, 3.0) * 2 - risk_penalty


def _qualifies(e: Dict[str, Any], cfg: CouponConfig) -> bool:
    if not e.get("play") or not e.get("ako_candidate"):
        return False
    if str(e.get("recommended_action")) == "SKIP":
        return False
    if float(e.get("confidence") or 0) < cfg.min_confidence:
        return False
    if float(e.get("value_rating") or 0) < cfg.min_value_rating:
        return False
    return RISK_ORDER.get(str(e.get("risk", "NO_BET")), 3) <= RISK_ORDER[cfg.max_risk]


def _dedupe_by_match(evals: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best: Dict[str, Dict[str, Any]] = {}
    for e in evals:
        key = str(e.get("match", "")).lower().strip()
        if not key:
            continue
        if key not in best or _score(e) > _score(best[key]):
            best[key] = e
    return list(best.values())


def build_ako_coupons(evaluations: Iterable[Dict[str, Any]], configs: List[CouponConfig] | None = None) -> Dict[str, Any]:
    configs = configs or DEFAULT_CONFIGS
    pool = _dedupe_by_match(evaluations)
    coupons: List[Dict[str, Any]] = []
    for cfg in configs:
        legs = sorted([e for e in pool if _qualifies(e, cfg)], key=_score, reverse=True)[: cfg.legs]
        if len(legs) < 2:
            continue
        total_odds = math.prod(float(e.get("odds") or 1) for e in legs)
        avg_conf = sum(float(e.get("confidence") or 0) for e in legs) / len(legs)
        avg_value = sum(float(e.get("value_rating") or 0) for e in legs) / len(legs)
        coupons.append({
            "coupon_name": cfg.name,
            "legs_count": len(legs),
            "total_odds": round(total_odds, 3),
            "avg_confidence": round(avg_conf, 2),
            "avg_value_rating": round(avg_value, 2),
            "risk_note": "AKO zwiększa wariancję; grać niższą stawką niż single.",
            "legs": [
                {
                    "match": e.get("match"),
                    "league": e.get("league"),
                    "market": e.get("market"),
                    "odds": e.get("odds"),
                    "confidence": e.get("confidence"),
                    "value_rating": e.get("value_rating"),
                    "risk": e.get("risk"),
                    "reason": e.get("reason"),
                }
                for e in legs
            ],
        })
    no_bets = [e for e in pool if not e.get("play") or str(e.get("recommended_action")) == "SKIP"]
    singles = sorted([e for e in pool if e.get("single_candidate") and e.get("play")], key=_score, reverse=True)[:10]
    return {"coupons": coupons, "best_singles": singles, "no_bet_count": len(no_bets)}
