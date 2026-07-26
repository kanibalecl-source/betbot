"""Read-only market-data integrity audit and training admission gate.

The audit never edits source histories, odds snapshots or model artifacts.  It
only writes an atomic derived report consumed by the autonomous governors.
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from market_data_integrity_v13 import SCHEMA_VERSION, policy_for as integrity_policy
from multisport_quality_v12 import SUPPORTED_SPORTS, policy_for as quality_policy
from storage_paths import get_data_dir


REPORT_SCHEMA = "betbot.market_integrity_audit.v13"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truthy(value: Any) -> bool:
    return isinstance(value, bool) and value or str(value or "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if result == result else None
    except (TypeError, ValueError):
        return None


def _minimum_observations(sport: str) -> int:
    default = quality_policy(sport).candidate_minimum_rows
    return max(
        50,
        int(os.getenv(f"BETBOT_V13_{sport.upper()}_MIN_TRAINING_OBSERVATIONS", str(default))),
    )


def _atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary, path)


def _current_football_rows(root: Path) -> list[dict[str, Any]]:
    for name in ("auto_all_picks.csv", "ai_picks.csv"):
        path = root / name
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]
        except Exception:
            continue
    return []


def _football_evidence(root: Path) -> list[dict[str, Any]]:
    """Persist unique derived consensus evidence while leaving source CSVs intact."""
    path = root / "quality_retraining" / "market_integrity_football_v13.jsonl"
    allowed_fields = {
        "market_integrity_schema",
        "market_integrity_status",
        "market_consensus_id",
        "market_bookmaker_count",
        "market_probability_dispersion",
        "market_average_overround",
        "bookmaker_verified",
        "bookmaker_scope",
        "market_scope",
        "odds_observed_at",
    }
    evidence: dict[str, dict[str, Any]] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            value = json.loads(line)
            key = str(value.get("market_consensus_id") or "").strip()
            if key:
                evidence[key] = dict(value)
    except Exception:
        pass
    new_rows: list[dict[str, Any]] = []
    for row in _current_football_rows(root):
        key = str(row.get("market_consensus_id") or "").strip()
        if not key or key in evidence:
            continue
        clean = {field: row.get(field) for field in allowed_fields}
        clean["captured_at"] = _now()
        evidence[key] = clean
        new_rows.append(clean)
    if new_rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for row in new_rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    return list(evidence.values())


def _shadow_rows(root: Path, sport: str) -> list[dict[str, Any]]:
    path = root / sport / f"{sport}_shadow.sqlite3"
    if not path.exists():
        return []
    uri = f"file:{path.as_posix()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=5) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT market_schema, bookmaker_count, probability_dispersion,
                       average_overround, observed_at
                FROM market_consensus_snapshots
                ORDER BY observed_at DESC
                """
            ).fetchall()
            return [dict(row) for row in rows]
    except (sqlite3.Error, OSError):
        return []


def _evaluate(rows: Iterable[Mapping[str, Any]], sport: str) -> dict[str, Any]:
    policy = integrity_policy(sport, outcomes=3 if sport == "football" else 2)
    minimum = _minimum_observations(sport)
    reasons: Counter[str] = Counter()
    admitted = 0
    v13_observed = 0
    dispersion_values: list[float] = []
    overround_values: list[float] = []
    for row in rows:
        schema = str(
            row.get("market_integrity_schema") or row.get("market_schema") or ""
        ).strip()
        status = str(row.get("market_integrity_status") or "").strip().upper()
        if SCHEMA_VERSION not in schema and not schema.endswith(".v13"):
            reasons["legacy_or_missing_v13_provenance"] += 1
            continue
        v13_observed += 1
        count = int(_number(row.get("market_bookmaker_count") or row.get("bookmaker_count")) or 0)
        dispersion = _number(
            row.get("market_probability_dispersion") or row.get("probability_dispersion")
        )
        overround = _number(row.get("market_average_overround") or row.get("average_overround"))
        if sport == "football":
            if status != "PASS":
                reasons["market_integrity_not_pass"] += 1
                continue
            if not _truthy(row.get("bookmaker_verified")):
                reasons["unverified_bookmaker"] += 1
                continue
            if str(row.get("bookmaker_scope", "")).strip() != "POLAND_ALLOWLIST":
                reasons["invalid_bookmaker_scope"] += 1
                continue
            if str(row.get("market_scope", "")).strip() != "FULL_MATCH":
                reasons["invalid_market_scope"] += 1
                continue
            if not str(row.get("market_consensus_id") or "").strip():
                reasons["missing_consensus_id"] += 1
                continue
        if count < policy.minimum_bookmakers:
            reasons["insufficient_bookmakers"] += 1
            continue
        if dispersion is None or dispersion > policy.maximum_probability_dispersion:
            reasons["excessive_probability_dispersion"] += 1
            continue
        admitted += 1
        dispersion_values.append(dispersion)
        if overround is not None:
            overround_values.append(overround)
    rejected = max(0, v13_observed - admitted)
    pass_rate = admitted / v13_observed if v13_observed else 0.0
    ready = admitted >= minimum and pass_rate >= 0.95
    status = "HEALTHY" if ready else (
        "DEGRADED" if v13_observed and pass_rate < 0.95 else "WAITING_QUALITY_DATA"
    )
    return {
        "sport": sport,
        "status": status,
        "training_admission_ready": ready,
        "v13_observations": v13_observed,
        "admitted_observations": admitted,
        "required_observations": minimum,
        "quarantined_observations": rejected,
        "pass_rate": round(pass_rate, 6),
        "average_probability_dispersion": (
            round(sum(dispersion_values) / len(dispersion_values), 8)
            if dispersion_values else None
        ),
        "average_overround": (
            round(sum(overround_values) / len(overround_values), 8)
            if overround_values else None
        ),
        "rejection_reasons": dict(reasons),
        "minimum_bookmakers": policy.minimum_bookmakers,
        "maximum_probability_dispersion": policy.maximum_probability_dispersion,
    }


class MarketIntegrityAuditV13:
    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.root = Path(data_dir or get_data_dir()).resolve()
        self.path = self.root / "quality_retraining" / "market_integrity_v13.json"

    def run(self) -> dict[str, Any]:
        sports = {
            "football": _evaluate(_football_evidence(self.root), "football"),
            "volleyball": _evaluate(_shadow_rows(self.root, "volleyball"), "volleyball"),
            "handball": _evaluate(_shadow_rows(self.root, "handball"), "handball"),
        }
        payload = {
            "schema_version": REPORT_SCHEMA,
            "market_contract": SCHEMA_VERSION,
            "status": (
                "HEALTHY"
                if all(item["training_admission_ready"] for item in sports.values())
                else "COLLECTING_OR_QUARANTINED"
            ),
            "updated_at": _now(),
            "sports": sports,
            "source_history_modified": False,
            "active_model_modified": False,
            "financial_execution_modified": False,
        }
        _atomic(self.path, payload)
        return payload


def sport_training_ready(data_dir: str | Path, sport: str) -> bool:
    """Return False on missing, malformed or stale/legacy audit evidence."""
    path = Path(data_dir) / "quality_retraining" / "market_integrity_v13.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        item = payload["sports"][sport]
        updated = datetime.fromisoformat(
            str(payload.get("updated_at", "")).replace("Z", "+00:00")
        )
        if updated.tzinfo is None:
            return False
        age = (datetime.now(timezone.utc) - updated.astimezone(timezone.utc)).total_seconds()
        max_age = max(
            300, int(os.getenv("BETBOT_V13_AUDIT_MAX_AGE_SECONDS", "10800"))
        )
        return (
            payload.get("schema_version") == REPORT_SCHEMA
            and item.get("training_admission_ready") is True
            and 0 <= age <= max_age
        )
    except Exception:
        return False
