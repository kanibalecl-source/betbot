from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


def _num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


@dataclass
class SourceQualityReport:
    provider: str
    quality_score: float
    completeness: float
    freshness: float
    consistency: float
    coverage: float
    missing_fields: List[str]
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SourceQualityEngine:
    """Production-safe data quality scorer.

    It does not pretend that every feed is perfect. It scores each payload and
    gives the rest of the bot a measurable confidence level. This is used by
    xG, ML and risk modules to downweight poor data instead of blindly trusting it.
    """

    REQUIRED_FIELDS = ["fixture_id", "home_team", "away_team", "league", "start_time"]
    FOOTBALL_FIELDS = [
        "home_shots", "away_shots", "home_shots_on_target", "away_shots_on_target",
        "home_dangerous_attacks", "away_dangerous_attacks", "home_possession", "away_possession",
    ]

    def evaluate(self, payload: Dict[str, Any], provider: str = "unknown") -> Dict[str, Any]:
        report = self.report(payload, provider)
        return report.to_dict()

    def report(self, payload: Dict[str, Any], provider: str = "unknown") -> SourceQualityReport:
        missing = [f for f in self.REQUIRED_FIELDS if payload.get(f) in (None, "")]
        known = sum(1 for f in self.REQUIRED_FIELDS + self.FOOTBALL_FIELDS if payload.get(f) not in (None, ""))
        total = len(self.REQUIRED_FIELDS) + len(self.FOOTBALL_FIELDS)
        completeness = max(0.0, min(1.0, known / total))
        coverage = max(0.0, min(1.0, 1.0 - len(missing) / max(1, len(self.REQUIRED_FIELDS))))
        freshness = self._freshness(payload)
        consistency, warnings = self._consistency(payload)
        quality = round((0.38 * completeness) + (0.22 * freshness) + (0.25 * consistency) + (0.15 * coverage), 4)
        return SourceQualityReport(
            provider=provider,
            quality_score=quality,
            completeness=round(completeness, 4),
            freshness=round(freshness, 4),
            consistency=round(consistency, 4),
            coverage=round(coverage, 4),
            missing_fields=missing,
            warnings=warnings,
        )

    def merge_reports(self, reports: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        rows = list(reports)
        if not rows:
            return {"quality_score": 0.0, "providers": 0, "status": "NO_SOURCES"}
        score = sum(_num(r.get("quality_score")) for r in rows) / len(rows)
        best = max(rows, key=lambda r: _num(r.get("quality_score")))
        return {
            "quality_score": round(score, 4),
            "providers": len(rows),
            "best_provider": best.get("provider"),
            "best_provider_score": best.get("quality_score"),
            "status": "OK" if score >= 0.55 else "LOW_QUALITY",
            "reports": rows,
        }

    def _freshness(self, payload: Dict[str, Any]) -> float:
        raw = payload.get("updated_at") or payload.get("timestamp") or payload.get("fetched_at")
        if not raw:
            return 0.55
        try:
            if isinstance(raw, (int, float)):
                dt = datetime.fromtimestamp(float(raw), timezone.utc)
            else:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            age_min = abs((datetime.now(timezone.utc) - dt).total_seconds()) / 60.0
            if age_min <= 10: return 1.0
            if age_min <= 60: return 0.85
            if age_min <= 360: return 0.65
            if age_min <= 1440: return 0.45
            return 0.25
        except Exception:
            return 0.50

    def _consistency(self, payload: Dict[str, Any]) -> tuple[float, List[str]]:
        warnings: List[str] = []
        score = 1.0
        hs, a_s = _num(payload.get("home_shots"), -1), _num(payload.get("away_shots"), -1)
        hsot, asot = _num(payload.get("home_shots_on_target"), -1), _num(payload.get("away_shots_on_target"), -1)
        hp, ap = _num(payload.get("home_possession"), -1), _num(payload.get("away_possession"), -1)
        if hs >= 0 and hsot > hs:
            score -= 0.25; warnings.append("home_shots_on_target_gt_shots")
        if a_s >= 0 and asot > a_s:
            score -= 0.25; warnings.append("away_shots_on_target_gt_shots")
        if hp >= 0 and ap >= 0 and abs((hp + ap) - 100) > 12:
            score -= 0.18; warnings.append("possession_sum_not_100")
        for k in ("home_goals", "away_goals", "home_shots", "away_shots"):
            if payload.get(k) is not None and _num(payload.get(k), 0) < 0:
                score -= 0.20; warnings.append(f"negative_{k}")
        return max(0.0, min(1.0, score)), warnings
