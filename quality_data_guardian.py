"""Read-only production data quality monitoring and feature impact evidence."""
from __future__ import annotations

import json
import math
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, Iterable

from agi_storage import DB_FILE, init_storage, log_event
from prediction_quality_pipeline import _database
from storage_paths import get_data_dir


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: Any):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _number(value: Any):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _atomic_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def _impact_report(history: sqlite3.Connection, evidence: sqlite3.Connection) -> Dict[str, Any]:
    settled = history.execute("""
        SELECT prediction_snapshot_id, probability, odds, clv, result, profit, stake
        FROM picks_history WHERE status='CLOSED' AND prediction_snapshot_id IS NOT NULL
    """).fetchall()
    outcomes = {}
    for row in settled:
        target = 1.0 if str(row["result"] or "").upper() in {"WIN", "WON", "1", "TRUE"} else 0.0
        outcomes[str(row["prediction_snapshot_id"])] = {
            "target": target, "probability": _number(row["probability"]),
            "clv": _number(row["clv"]), "profit": _number(row["profit"]),
            "stake": _number(row["stake"]) or 1.0,
        }
    latest = evidence.execute("""
        SELECT s.snapshot_id, s.raw_json FROM shadow_feature_ledger s
        JOIN (SELECT snapshot_id, max(recorded_at) AS recorded_at
              FROM shadow_feature_ledger GROUP BY snapshot_id) x
          ON x.snapshot_id=s.snapshot_id AND x.recorded_at=s.recorded_at
    """).fetchall()
    joined = []
    for row in latest:
        outcome = outcomes.get(str(row["snapshot_id"]))
        if not outcome:
            continue
        try:
            features = json.loads(row["raw_json"] or "{}")
        except Exception:
            features = {}
        joined.append((features, outcome))
    minimum = max(30, int(os.getenv("BETBOT_FEATURE_IMPACT_MIN_SAMPLES", "100")))
    feature_names = (
        "home_rest_days", "away_rest_days", "home_matches_last_14d",
        "away_matches_last_14d", "lineups_available", "injuries_count",
        "home_form_home", "away_form_away", "coach_change",
    )
    impacts = []
    for name in feature_names:
        usable = [(features.get(name), outcome) for features, outcome in joined if features.get(name) is not None]
        if len(usable) < minimum:
            impacts.append({"feature": name, "samples": len(usable), "status": "INSUFFICIENT_DATA"})
            continue
        numeric = [_number(value) for value, _ in usable]
        numeric = [value for value in numeric if value is not None]
        if not numeric:
            impacts.append({"feature": name, "samples": len(usable), "status": "NON_NUMERIC"})
            continue
        split = median(numeric)
        groups = {"low": [], "high": []}
        for value, outcome in usable:
            number = _number(value)
            if number is not None:
                groups["high" if number >= split else "low"].append(outcome)
        metrics = {}
        for label, rows in groups.items():
            probabilities = [(r["probability"], r["target"]) for r in rows if r["probability"] is not None]
            clv = [r["clv"] for r in rows if r["clv"] is not None]
            metrics[label] = {
                "samples": len(rows),
                "brier": round(mean((p - y) ** 2 for p, y in probabilities), 8) if probabilities else None,
                "mean_clv": round(mean(clv), 8) if clv else None,
                "yield": round(sum(r["profit"] or 0.0 for r in rows) / sum(r["stake"] for r in rows), 8) if rows else None,
            }
        impacts.append({
            "feature": name, "samples": len(usable), "status": "DIAGNOSTIC_ONLY",
            "split": split, "groups": metrics,
            "production_effect": "NONE_SHADOW_ONLY",
        })
    return {
        "generated_at": _now().isoformat(), "joined_settled_samples": len(joined),
        "minimum_samples_per_feature": minimum, "features": impacts,
        "warning": "Association report only; promotion still requires walk-forward and live shadow validation.",
    }


def run_guardian(data_dir: str | Path | None = None) -> Dict[str, Any]:
    init_storage()
    root = Path(data_dir or get_data_dir()).resolve()
    history = sqlite3.connect(DB_FILE)
    history.row_factory = sqlite3.Row
    evidence = sqlite3.connect(_database(root))
    evidence.row_factory = sqlite3.Row
    now = _now()
    try:
        total = history.execute("SELECT count(*) FROM picks_history").fetchone()[0]
        ledger_count = evidence.execute("SELECT count(*) FROM prediction_ledger").fetchone()[0]
        first_ledger = evidence.execute("SELECT min(recorded_at) FROM prediction_ledger").fetchone()[0]
        eligible_rows = history.execute(
            "SELECT prediction_snapshot_id FROM picks_history "
            "WHERE prediction_snapshot_id IS NOT NULL AND prediction_snapshot_id != ''",
        ).fetchall()
        ledger_ids = {str(row[0]) for row in evidence.execute("SELECT snapshot_id FROM prediction_ledger").fetchall()}
        eligible = len(eligible_rows)
        matched_ledger = sum(1 for row in eligible_rows if str(row[0] or "") in ledger_ids)
        due = history.execute(
            "SELECT count(*) FROM picks_history WHERE match_date < ? "
            "AND prediction_snapshot_id IS NOT NULL AND prediction_snapshot_id != ''",
            ((now - timedelta(hours=4)).isoformat(),),
        ).fetchone()[0]
        settled = history.execute(
            "SELECT count(*) FROM picks_history WHERE match_date < ? AND status='CLOSED' "
            "AND prediction_snapshot_id IS NOT NULL AND prediction_snapshot_id != ''",
            ((now - timedelta(hours=4)).isoformat(),),
        ).fetchone()[0]
        closed = history.execute(
            "SELECT count(*) FROM picks_history WHERE status='CLOSED' "
            "AND prediction_snapshot_id IS NOT NULL AND prediction_snapshot_id != ''"
        ).fetchone()[0]
        closed_with_closing = history.execute(
            "SELECT count(*) FROM picks_history WHERE status='CLOSED' AND closing_odds > 1 "
            "AND prediction_snapshot_id IS NOT NULL AND prediction_snapshot_id != ''"
        ).fetchone()[0]
        feature_rows = evidence.execute("SELECT completeness FROM shadow_feature_ledger").fetchall()
        odds_stages = {
            str(row[0]): int(row[1]) for row in evidence.execute(
                "SELECT stage, count(*) FROM odds_observation_ledger GROUP BY stage"
            ).fetchall()
        }
        latest_prediction = evidence.execute("SELECT max(recorded_at) FROM prediction_ledger").fetchone()[0]
        latest_closing = evidence.execute("SELECT max(recorded_at) FROM closing_odds_ledger").fetchone()[0]
        recent_events = history.execute(
            "SELECT event_type, count(*) FROM learning_events WHERE created_at >= ? GROUP BY event_type",
            ((now - timedelta(hours=24)).isoformat(timespec="seconds"),),
        ).fetchall()
        event_counts = {str(row[0]): int(row[1]) for row in recent_events}
        ledger_coverage = _ratio(matched_ledger, eligible)
        settlement_coverage = _ratio(settled, due)
        closing_coverage = _ratio(closed_with_closing, closed)
        feature_completeness = round(mean(float(row[0] or 0) for row in feature_rows), 6) if feature_rows else 0.0
        thresholds = {
            "ledger_coverage": float(os.getenv("BETBOT_GUARDIAN_MIN_LEDGER_COVERAGE", "0.99")),
            "settlement_coverage": float(os.getenv("BETBOT_GUARDIAN_MIN_SETTLEMENT_COVERAGE", "0.95")),
            "closing_coverage": float(os.getenv("BETBOT_QUALITY_MIN_CLOSING_COVERAGE", "0.80")),
            "maximum_api_errors_24h": int(os.getenv("BETBOT_GUARDIAN_MAX_API_ERRORS_24H", "5")),
        }
        alerts = []
        for name, value in (("ledger_coverage", ledger_coverage),
                            ("settlement_coverage", settlement_coverage),
                            ("closing_coverage", closing_coverage)):
            if (eligible if name == "ledger_coverage" else due if name == "settlement_coverage" else closed) and value < thresholds[name]:
                alerts.append({"severity": "WARNING", "code": name.upper(),
                               "value": value, "required": thresholds[name]})
        api_errors = (
            event_counts.get("settlement_error", 0)
            + event_counts.get("closing_odds_error", 0)
            + event_counts.get("scheduled_odds_error", 0)
        )
        if api_errors > thresholds["maximum_api_errors_24h"]:
            alerts.append({"severity": "WARNING", "code": "API_OR_SETTLEMENT_ERRORS_24H",
                           "count": api_errors, "allowed": thresholds["maximum_api_errors_24h"]})
        report = {
            "generated_at": now.isoformat(),
            "status": "HEALTHY" if not alerts else "ATTENTION",
            "production_model_changed": False, "automatic_promotion": False,
            "metrics": {
                "history_records": total, "ledger_eligible_records": eligible,
                "ledger_matched_records": matched_ledger, "prediction_ledger_records": ledger_count,
                "ledger_coverage": ledger_coverage, "settlement_coverage": settlement_coverage,
                "closing_odds_coverage": closing_coverage,
                "shadow_feature_records": len(feature_rows),
                "mean_shadow_feature_completeness": feature_completeness,
                "odds_snapshot_stages": odds_stages,
                "latest_prediction_snapshot": latest_prediction,
                "latest_closing_snapshot": latest_closing,
            },
            "thresholds": thresholds, "events_24h": event_counts, "alerts": alerts,
            "training_readiness": {
                "minimum_settled": 300,
                "settled": closed,
                "ready_for_validation": closed >= 300 and closing_coverage >= thresholds["closing_coverage"]
                    and settlement_coverage >= thresholds["settlement_coverage"],
                "auto_promote": False,
            },
        }
        target = root / "quality_retraining"
        _atomic_json(target / "data_quality_guardian.json", report)
        impact = _impact_report(history, evidence)
        _atomic_json(target / "shadow_feature_impact.json", impact)
        log_event("data_quality_guardian", {"status": report["status"], "alerts": alerts,
                                              "metrics": report["metrics"]})
        return {"status": report["status"], "alerts": len(alerts),
                "training_ready": report["training_readiness"]["ready_for_validation"]}
    finally:
        history.close()
        evidence.close()


if __name__ == "__main__":
    print(json.dumps(run_guardian(), ensure_ascii=False, indent=2))
