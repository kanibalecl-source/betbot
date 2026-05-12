from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

from source_quality_engine import SourceQualityEngine
from enterprise_data_feeds import EnterpriseDataFeeds


@dataclass
class SourceFetchResult:
    provider: str
    ok: bool
    payload: Dict[str, Any]
    error: Optional[str] = None
    status_code: Optional[int] = None
    fetched_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MultiSourceIngestion:
    """Real multi-source ingestion layer with retries, cache and normalization.

    Supported out of the box:
    - API-Football when API_KEY is available.
    - Local JSON/CSV snapshots from data/providers for Understat/Sofascore/Fotmob-style files.
    - Manual payloads passed from existing bot modules.

    The class is safe when API keys are missing: it returns clear source status
    instead of crashing the whole prediction cycle.
    """

    DEFAULT_SOURCES = ["api_football", "local_understat", "local_sofascore", "local_fotmob"]

    def __init__(self, data_dir: str | Path = "data", timeout: int = 12, retries: int = 2):
        self.data_dir = Path(data_dir)
        self.cache_dir = self.data_dir / "source_cache"
        self.provider_dir = self.data_dir / "providers"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.provider_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.retries = retries
        self.quality = SourceQualityEngine()
        self.enterprise_feeds = EnterpriseDataFeeds(data_dir=self.data_dir)

    def fetch_fixture(self, fixture_id: str | int, sources: Optional[List[str]] = None) -> Dict[str, Any]:
        sources = sources or self.DEFAULT_SOURCES
        results: List[Dict[str, Any]] = []
        for source in sources:
            if source == "api_football":
                results.append(self._fetch_api_football(fixture_id).to_dict())
            elif source.startswith("local_"):
                provider = source.replace("local_", "")
                results.append(self._fetch_local_provider(fixture_id, provider).to_dict())
        merged = self.merge_sources([r for r in results if r.get("ok")])
        enterprise = self.enterprise_feeds.fetch_all(fixture_id)
        if enterprise.get("status") == "ENTERPRISE_FEEDS_MERGED":
            merged.update({k: v for k, v in enterprise.items() if v not in (None, "", [], {})})
        quality_reports = [self.quality.evaluate(r.get("payload", {}), r.get("provider", "unknown")) for r in results if r.get("ok")]
        merged["source_quality"] = self.quality.merge_reports(quality_reports)
        merged["source_results"] = results
        self._write_cache(f"fixture_{fixture_id}_merged", merged)
        return merged

    def merge_sources(self, results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        rows = [r.get("payload", r) for r in results if r]
        if not rows:
            return {"status": "NO_SOURCE_DATA", "data_quality": 0.0}
        scored = [(self.quality.evaluate(row, row.get("provider", "unknown")), row) for row in rows]
        scored.sort(key=lambda x: x[0]["quality_score"], reverse=True)
        merged: Dict[str, Any] = {}
        # priority: highest quality non-empty value wins
        keys = sorted(set().union(*(row.keys() for _, row in scored)))
        for key in keys:
            for _, row in scored:
                val = row.get(key)
                if val not in (None, "", [], {}):
                    merged[key] = val
                    break
        merged["providers_used"] = [row.get("provider", "unknown") for _, row in scored]
        merged["data_quality"] = scored[0][0]["quality_score"]
        merged["status"] = "MERGED"
        merged["updated_at"] = datetime.now(timezone.utc).isoformat()
        return merged

    def _fetch_api_football(self, fixture_id: str | int) -> SourceFetchResult:
        api_key = os.getenv("API_KEY") or os.getenv("API_FOOTBALL_KEY")
        now = datetime.now(timezone.utc).isoformat()
        if not api_key:
            return SourceFetchResult("api_football", False, {}, "missing API_KEY", fetched_at=now)
        url = "https://v3.football.api-sports.io/fixtures"
        params = {"id": fixture_id}
        headers = {"x-apisports-key": api_key}
        last_err = None
        for attempt in range(self.retries + 1):
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=self.timeout)
                if resp.status_code == 200:
                    raw = resp.json()
                    payload = self._normalize_api_football(raw, fixture_id)
                    payload["provider"] = "api_football"
                    payload["fetched_at"] = now
                    return SourceFetchResult("api_football", True, payload, status_code=resp.status_code, fetched_at=now)
                last_err = f"HTTP {resp.status_code}: {resp.text[:180]}"
            except Exception as exc:
                last_err = str(exc)
            time.sleep(0.6 * (attempt + 1))
        return SourceFetchResult("api_football", False, {}, last_err, fetched_at=now)

    def _normalize_api_football(self, raw: Dict[str, Any], fixture_id: str | int) -> Dict[str, Any]:
        response = raw.get("response") or []
        item = response[0] if response else {}
        fixture = item.get("fixture", {})
        league = item.get("league", {})
        teams = item.get("teams", {})
        goals = item.get("goals", {})
        stats = item.get("statistics") or []
        out: Dict[str, Any] = {
            "fixture_id": str(fixture_id),
            "league": league.get("name"),
            "country": league.get("country"),
            "start_time": fixture.get("date"),
            "status": (fixture.get("status") or {}).get("short"),
            "home_team": (teams.get("home") or {}).get("name"),
            "away_team": (teams.get("away") or {}).get("name"),
            "home_goals": goals.get("home"),
            "away_goals": goals.get("away"),
        }
        for block in stats:
            team_name = ((block.get("team") or {}).get("name") or "").lower()
            prefix = "home" if team_name and team_name == str(out.get("home_team", "")).lower() else "away"
            for s in block.get("statistics") or []:
                typ = str(s.get("type", "")).lower()
                val = s.get("value")
                if isinstance(val, str) and val.endswith("%"):
                    val = val.replace("%", "")
                if "shots on goal" in typ: out[f"{prefix}_shots_on_target"] = val
                elif typ == "total shots": out[f"{prefix}_shots"] = val
                elif "ball possession" in typ: out[f"{prefix}_possession"] = val
                elif "dangerous attacks" in typ: out[f"{prefix}_dangerous_attacks"] = val
                elif "corner" in typ: out[f"{prefix}_corners"] = val
        return out

    def _fetch_local_provider(self, fixture_id: str | int, provider: str) -> SourceFetchResult:
        now = datetime.now(timezone.utc).isoformat()
        for ext in ("json",):
            path = self.provider_dir / provider / f"{fixture_id}.{ext}"
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    data.setdefault("fixture_id", str(fixture_id))
                    data["provider"] = provider
                    data["fetched_at"] = now
                    return SourceFetchResult(provider, True, data, fetched_at=now)
                except Exception as exc:
                    return SourceFetchResult(provider, False, {}, str(exc), fetched_at=now)
        return SourceFetchResult(provider, False, {}, "local provider file not found", fetched_at=now)

    def _write_cache(self, key: str, payload: Dict[str, Any]) -> None:
        safe = hashlib.sha1(str(key).encode()).hexdigest()[:16]
        (self.cache_dir / f"{safe}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
