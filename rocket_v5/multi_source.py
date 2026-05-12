from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


@dataclass
class SourceSpec:
    name: str
    priority: int
    enabled: bool = True
    api_key_env: str = ""
    role: str = "general"
    notes: str = ""


@dataclass
class SourceAudit:
    score: float
    sources_used: List[str]
    conflicts: List[str]
    missing_core_fields: List[str]
    missing_power_fields: List[str]
    warnings: List[str]


DEFAULT_SOURCES = [
    SourceSpec("api_football", 10, True, "API_FOOTBALL_KEY", "fixtures_results_lineups_stats"),
    SourceSpec("understat_or_xg", 15, True, "UNDERSTAT_KEY", "shot_xg"),
    SourceSpec("fotmob", 25, True, "FOTMOB_KEY", "lineups_shots_momentum"),
    SourceSpec("sofascore_unofficial", 30, False, "", "live_events_momentum", "Use only if permitted by ToS."),
    SourceSpec("football_data", 40, True, "FOOTBALL_DATA_KEY", "backup_results"),
    SourceSpec("odds_api", 80, True, "ODDS_API_KEY", "odds_only_not_model_features"),
    SourceSpec("open_meteo", 90, True, "", "weather"),
]


class MultiSourceHubV5:
    CORE_FIELDS = ["match_id", "home_team", "away_team", "league", "kickoff"]
    POWER_FIELDS = [
        "home_xg", "away_xg", "home_xga", "away_xga", "home_shots", "away_shots",
        "home_sot", "away_sot", "home_big_chances", "away_big_chances", "events",
        "lineups", "injuries", "home_ppda", "away_ppda", "weather_drag"
    ]

    def __init__(self, data_dir: str | Path = "data/rocket_v5", sources: Optional[List[SourceSpec]] = None):
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.sources = sources or DEFAULT_SOURCES
        self.session = requests.Session() if requests else None

    def provider_status(self) -> List[Dict[str, Any]]:
        return [
            {**asdict(s), "api_key_present": bool(os.getenv(s.api_key_env)) if s.api_key_env else True}
            for s in sorted(self.sources, key=lambda x: x.priority)
        ]

    def merge_payloads(self, payloads: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {"sources_used": [], "source_confidence": {}}
        conflicts: List[str] = []
        for payload in payloads:
            if not payload:
                continue
            source = payload.get("source") or payload.get("provider") or "manual"
            if source not in merged["sources_used"]:
                merged["sources_used"].append(source)
            priority = next((s.priority for s in self.sources if s.name == source), 50)
            merged["source_confidence"][source] = round(1 / max(priority, 1), 4)
            for key, value in payload.items():
                if key in {"source", "provider"} or value in (None, "", [], {}):
                    continue
                if key in merged and merged[key] not in (None, "", [], {}) and merged[key] != value:
                    if key not in ["sources_used", "source_confidence"]:
                        conflicts.append(f"{key}: kept={merged[key]} ignored={value} source={source}")
                    continue
                merged[key] = value
        merged["conflicts"] = conflicts[:50]
        return merged

    def audit(self, match: Dict[str, Any]) -> SourceAudit:
        missing_core = [f for f in self.CORE_FIELDS if match.get(f) in (None, "", [], {})]
        missing_power = [f for f in self.POWER_FIELDS if match.get(f) in (None, "", [], {})]
        coverage = 1 - len(missing_power) / max(len(self.POWER_FIELDS), 1)
        core_penalty = 0.20 * len(missing_core)
        score = max(0.0, min(1.0, 0.25 + coverage * 0.75 - core_penalty))
        warnings = []
        if "odds" in match or "bookmaker_odds" in match:
            warnings.append("Odds detected in payload. V5 will ignore them for model features and use them only for market comparison.")
        if not match.get("events"):
            warnings.append("No event/shot feed: advanced xG falls back to aggregate team features.")
        return SourceAudit(round(score, 4), match.get("sources_used", ["manual"]), match.get("conflicts", []), missing_core, missing_power, warnings)

    def save_snapshot(self, match: Dict[str, Any]) -> Path:
        match_id = str(match.get("match_id") or f"match_{int(time.time())}")
        path = self.raw_dir / f"{match_id}_{int(time.time())}.json"
        path.write_text(json.dumps(match, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
