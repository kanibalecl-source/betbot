from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .config import RocketConfig, load_config, env_key


@dataclass
class DataQualityReport:
    score: float
    sources_used: list[str]
    missing_fields: list[str]
    warnings: list[str]


class DataHubV4:
    """Provider-agnostic data layer.

    This class accepts already fetched match dictionaries and can also be extended
    with real API calls. It never reads bookmaker odds for model features. Odds
    belong only in market comparison.
    """

    REQUIRED_FIELDS = ["home_team", "away_team", "league"]
    HIGH_VALUE_FIELDS = [
        "home_recent", "away_recent", "home_shots", "away_shots", "home_sot",
        "away_sot", "home_xg", "away_xg", "lineups", "injuries", "events",
        "home_dangerous_attacks", "away_dangerous_attacks", "home_ppda", "away_ppda",
    ]

    def __init__(self, config: Optional[RocketConfig] = None):
        self.config = config or load_config()
        self.session = requests.Session()

    def save_raw_snapshot(self, match_id: str, data: Dict[str, Any]) -> Path:
        path = self.config.data_dir / "raw" / f"{match_id}_{int(time.time())}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def quality_report(self, match: Dict[str, Any]) -> DataQualityReport:
        missing = [f for f in self.REQUIRED_FIELDS if not match.get(f)]
        missing_high = [f for f in self.HIGH_VALUE_FIELDS if match.get(f) in (None, "", [])]
        base = 0.30 if not missing else 0.10
        coverage = 1.0 - (len(missing_high) / max(len(self.HIGH_VALUE_FIELDS), 1))
        score = min(1.0, base + 0.70 * coverage)
        warnings = []
        if match.get("home_xg") is None or match.get("away_xg") is None:
            warnings.append("No direct xG source; estimating xG from proxy features.")
        if not match.get("lineups"):
            warnings.append("No confirmed lineups; lineup adjustment disabled or estimated.")
        if not match.get("events"):
            warnings.append("No shot/event feed; shot quality model uses team aggregates.")
        sources = match.get("sources_used") or ["input_payload"]
        return DataQualityReport(round(score, 4), sources, missing + missing_high, warnings)

    def merge_sources(self, *payloads: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {"sources_used": []}
        for p in payloads:
            if not p:
                continue
            src = p.get("source") or p.get("provider") or "unknown"
            if src not in merged["sources_used"]:
                merged["sources_used"].append(src)
            for k, v in p.items():
                if k in {"source", "provider"}:
                    continue
                if v not in (None, "", []):
                    merged[k] = v
        return merged

    def provider_status(self) -> list[dict]:
        out = []
        for p in sorted(self.config.providers, key=lambda x: x.priority):
            out.append({
                "name": p.name,
                "enabled": p.enabled,
                "api_key_configured": bool(env_key(p.api_key_env)) if p.api_key_env else None,
                "priority": p.priority,
                "notes": p.notes,
            })
        return out
