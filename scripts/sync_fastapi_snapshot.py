"""Publish a bounded, validated snapshot to the separate FastAPI service.

This process only reads the authoritative volume. It never edits source
history, settlements, candidates or active models.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pandas as pd

from storage_paths import DATA_DIR


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _clean(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def football_records(limit: int = 500) -> list[dict[str, Any]]:
    candidates = [DATA_DIR / "auto_all_picks.csv", DATA_DIR / "ai_picks.csv"]
    for path in candidates:
        try:
            frame = pd.read_csv(path).tail(limit)
        except Exception:
            continue
        rows = []
        for index, row in frame.iterrows():
            raw = {str(key): _clean(value) for key, value in row.to_dict().items()}
            home = str(raw.get("home_team") or raw.get("home") or "").strip()
            away = str(raw.get("away_team") or raw.get("away") or "").strip()
            source_match_status = str(raw.get("status") or "").strip().upper()
            source_result = str(raw.get("result") or "").strip().upper()
            if source_result in {"WON", "LOST", "VOID", "PUSH"}:
                api_status = "CLOSED"
                api_result = source_result
            else:
                # Football history uses status for the match phase (NS/1H/2H),
                # while FastAPI status describes the lifecycle of a pick.
                api_status = "OPEN"
                api_result = "PENDING"
            raw.update(
                {
                    "sport": "football",
                    "pick_id": str(raw.get("pick_id") or raw.get("id") or f"football-{index}"),
                    "match_name": str(raw.get("match_name") or raw.get("match") or f"{home} vs {away}"),
                    "market": str(raw.get("market") or raw.get("typ") or ""),
                    "bookmaker_odds": raw.get("bookmaker_odds", raw.get("kurs_buk", raw.get("odds"))),
                    "bookmaker": raw.get("bookmaker") or raw.get("bookmaker_name"),
                    "bookmaker_id": raw.get("bookmaker_id"),
                    "bookmaker_scope": raw.get("bookmaker_scope"),
                    "bookmaker_verified": raw.get("bookmaker_verified", False),
                    "odds_bet_id": raw.get("odds_bet_id"),
                    "odds_bet_name": raw.get("odds_bet_name"),
                    "market_scope": raw.get("market_scope"),
                    "odds_observed_at": raw.get("odds_observed_at"),
                    "market_integrity_schema": raw.get("market_integrity_schema"),
                    "market_integrity_status": raw.get("market_integrity_status"),
                    "market_consensus_id": raw.get("market_consensus_id"),
                    "market_bookmaker_count": raw.get("market_bookmaker_count"),
                    "market_probability": raw.get("market_probability"),
                    "market_fair_odds": raw.get("market_fair_odds"),
                    "market_probability_dispersion": raw.get(
                        "market_probability_dispersion"
                    ),
                    "market_average_overround": raw.get("market_average_overround"),
                    "model_probability": raw.get(
                        "model_probability",
                        raw.get("probability", raw.get("confidence")),
                    ),
                    "status": api_status,
                    "result": api_result,
                    "source_match_status": source_match_status,
                }
            )
            rows.append(raw)
        return rows
    return []


def shadow_records(sport: str, limit: int = 500) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        if sport == "volleyball":
            from volleyball_v9.dashboard import load_volleyball_dashboard
            snapshot = load_volleyball_dashboard(pick_limit=limit)
        else:
            from handball_v11.dashboard import load_handball_dashboard
            snapshot = load_handball_dashboard(pick_limit=limit)
    except Exception as exc:
        return [], {"status": "READ_ERROR", "error_type": type(exc).__name__}
    records = []
    for item in snapshot.get("picks", []):
        row = dict(item)
        row["sport"] = sport
        row["pick_id"] = str(row.get("pick_key", ""))
        row["model_probability"] = row.get("model_probability")
        row["bookmaker_odds"] = row.get("bookmaker_odds")
        row["generated_at"] = row.get("generated_at") or row.get("created_at")
        records.append(row)
    return records, snapshot


def build_snapshot() -> dict[str, Any]:
    volleyball, volleyball_state = shadow_records("volleyball")
    handball, handball_state = shadow_records("handball")
    quality_root = DATA_DIR / "quality_retraining"
    autonomy = _read_json(quality_root / "autonomy_v11_state.json")
    multisport = _read_json(quality_root / "multisport_v12_audit.json")
    guardian = _read_json(quality_root / "data_quality_guardian.json")
    integrity = _read_json(quality_root / "market_integrity_v13.json")
    statuses: list[dict[str, Any]] = []
    for sport in ("football", "volleyball", "handball"):
        sport_quality = (
            multisport.get("sports", {}).get(sport, {})
            if isinstance(multisport.get("sports"), dict)
            else {}
        )
        statuses.extend(
            [
                {"sport": sport, "kind": "quality", "payload": sport_quality},
                {
                    "sport": sport,
                    "kind": "model",
                    "payload": (
                        autonomy if sport == "football"
                        else (volleyball_state if sport == "volleyball" else handball_state)
                    ),
                },
                {
                    "sport": sport,
                    "kind": "data_quality",
                    "payload": {
                        **(guardian if sport == "football" else sport_quality),
                        "market_integrity_v13": (
                            integrity.get("sports", {}).get(sport, {})
                            if isinstance(integrity.get("sports"), dict)
                            else {}
                        ),
                    },
                },
                {
                    "sport": sport,
                    "kind": "runtime",
                    "payload": (
                        volleyball_state if sport == "volleyball"
                        else handball_state if sport == "handball"
                        else {"status": autonomy.get("status", "WAITING")}
                    ),
                },
            ]
        )
    return {
        "source": "betbot-main-volume-readonly",
        "records": [*football_records(), *volleyball, *handball],
        "statuses": statuses,
    }


def publish_once() -> dict[str, Any]:
    import requests
    base_url = os.getenv("BETBOT_FASTAPI_URL", "").strip().rstrip("/")
    api_key = os.getenv("BETBOT_FASTAPI_API_KEY", "").strip()
    if not base_url or len(api_key) < 32:
        return {"status": "DISABLED_OR_INCOMPLETE_CONFIGURATION"}
    response = requests.post(
        f"{base_url}/api/v1/internal/sync",
        headers={"x-api-key": api_key},
        json=build_snapshot(),
        timeout=30,
    )
    response.raise_for_status()
    return {"status": "OK", **response.json()}


def main() -> int:
    interval = max(5, int(os.getenv("BETBOT_FASTAPI_SYNC_MINUTES", "30")))
    while True:
        try:
            print(json.dumps({"event": "FASTAPI_SNAPSHOT_SYNC", **publish_once()}), flush=True)
        except Exception as exc:
            print(
                json.dumps(
                    {"event": "FASTAPI_SNAPSHOT_SYNC_FAILED", "error_type": type(exc).__name__}
                ),
                flush=True,
            )
        time.sleep(interval * 60)


if __name__ == "__main__":
    raise SystemExit(main())
