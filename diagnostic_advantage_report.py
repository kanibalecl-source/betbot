"""Read-only diagnostic report for verified betting advantage.

The report consumes the derived ``quality_training`` dataset and writes only
derived JSON artifacts.  It never edits source history, settlements or the
active model.  The generated selection policy is deliberately conservative:
segments are blocked only after a meaningful sample and materially negative
out-of-sample evidence.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable, Mapping, Sequence

from storage_paths import get_data_dir


def _number(value: Any) -> float | None:
    try:
        number = float(str(value).replace("%", "").replace(",", ".").strip())
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _probability(value: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    if number > 1.0:
        number /= 100.0
    return number if 0.0 < number < 1.0 else None


def _target(value: Any) -> int | None:
    normalized = str(value or "").strip().upper()
    if normalized in {"1", "TRUE", "WIN", "WON"}:
        return 1
    if normalized in {"0", "FALSE", "LOSS", "LOST", "LOSE"}:
        return 0
    return None


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def load_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _wilson(successes: int, samples: int, confidence: float = 0.95) -> dict[str, float]:
    if samples <= 0:
        return {"lower": 0.0, "upper": 0.0, "confidence": confidence}
    z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
    rate = successes / samples
    denominator = 1.0 + z * z / samples
    centre = (rate + z * z / (2 * samples)) / denominator
    margin = z * math.sqrt((rate * (1 - rate) + z * z / (4 * samples)) / samples) / denominator
    return {
        "lower": round(max(0.0, centre - margin), 6),
        "upper": round(min(1.0, centre + margin), 6),
        "confidence": confidence,
    }


def _mean_ci(values: Sequence[float], confidence: float = 0.95) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "lower": 0.0, "upper": 0.0, "confidence": confidence}
    mean = sum(values) / len(values)
    if len(values) < 2:
        margin = 0.0
    else:
        variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
        margin = NormalDist().inv_cdf(0.5 + confidence / 2.0) * math.sqrt(variance / len(values))
    return {
        "mean": round(mean, 8),
        "lower": round(mean - margin, 8),
        "upper": round(mean + margin, 8),
        "confidence": confidence,
    }


def _ece(probabilities: Sequence[float], targets: Sequence[int], bins: int = 10) -> tuple[float, list[dict[str, Any]]]:
    reliability: list[dict[str, Any]] = []
    error = 0.0
    for index in range(max(2, bins)):
        low, high = index / bins, (index + 1) / bins
        positions = [
            pos for pos, probability in enumerate(probabilities)
            if low <= probability < high or (index == bins - 1 and probability == 1.0)
        ]
        if not positions:
            continue
        confidence = sum(probabilities[pos] for pos in positions) / len(positions)
        frequency = sum(targets[pos] for pos in positions) / len(positions)
        error += len(positions) / max(1, len(targets)) * abs(confidence - frequency)
        reliability.append({
            "range": f"{low:.1f}-{high:.1f}",
            "samples": len(positions),
            "mean_probability": round(confidence, 6),
            "hit_rate": round(frequency, 6),
            "calibration_gap": round(frequency - confidence, 6),
        })
    return round(error, 8), reliability


def _drawdown(profits: Sequence[float]) -> float:
    equity = peak = drawdown = 0.0
    for profit in profits:
        equity += profit
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return round(drawdown, 6)


def _normalized_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for position, row in enumerate(rows):
        probability = _probability(row.get("current_probability"))
        target = _target(row.get("target"))
        odds = _number(row.get("odds"))
        closing = _number(row.get("closing_odds"))
        normalized.append({
            **dict(row),
            "_position": position,
            "_time": _parse_time(row.get("timestamp")),
            "_probability": probability,
            "_target": target,
            "_odds": odds if odds is not None and odds > 1.0 else None,
            "_closing": closing if closing is not None and closing > 1.0 else None,
            "_market": str(row.get("market") or "UNKNOWN"),
            "_league": str(row.get("league") or "UNKNOWN"),
            "_source": str(row.get("source") or "UNKNOWN"),
        })
    return normalized


def data_integrity_audit(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = _normalized_rows(rows)
    record_ids = [str(row.get("record_id") or "") for row in normalized]
    populated_ids = [value for value in record_ids if value]
    duplicate_ids = sum(count - 1 for count in Counter(populated_ids).values() if count > 1)
    conflict_map: dict[str, set[int]] = defaultdict(set)
    fixture_market_sources: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in normalized:
        record_id = str(row.get("record_id") or "")
        if record_id and row["_target"] is not None:
            conflict_map[record_id].add(int(row["_target"]))
        fixture_id = str(row.get("fixture_id") or "")
        if fixture_id:
            fixture_market_sources[(fixture_id, row["_market"])].add(row["_source"])
    missing = {
        "timestamp": sum(row["_time"] is None for row in normalized),
        "record_id": sum(not str(row.get("record_id") or "") for row in normalized),
        "fixture_id": sum(not str(row.get("fixture_id") or "") for row in normalized),
        "market": sum(row["_market"] == "UNKNOWN" for row in normalized),
        "league": sum(row["_league"] == "UNKNOWN" for row in normalized),
        "probability": sum(row["_probability"] is None for row in normalized),
        "target": sum(row["_target"] is None for row in normalized),
        "odds": sum(row["_odds"] is None for row in normalized),
        "closing_odds": sum(row["_closing"] is None for row in normalized),
    }
    chronological = [row["_time"] for row in normalized if row["_time"] is not None]
    out_of_order = sum(current < previous for previous, current in zip(chronological, chronological[1:]))
    critical = duplicate_ids > 0 or any(len(values) > 1 for values in conflict_map.values())
    return {
        "status": "FAIL" if critical else "PASS_WITH_WARNINGS" if any(missing.values()) else "PASS",
        "rows": len(normalized),
        "duplicate_record_ids": duplicate_ids,
        "conflicting_targets": sum(len(values) > 1 for values in conflict_map.values()),
        "fixture_market_multi_source_groups": sum(len(values) > 1 for values in fixture_market_sources.values()),
        "out_of_order_timestamps": out_of_order,
        "missing_counts": missing,
        "source_history_mutated": False,
        "leakage_controls": {
            "chronological_only": True,
            "fixture_grouping_required_in_walk_forward": True,
            "closing_odds_excluded_from_model_features": True,
            "target_excluded_from_features": True,
        },
    }


def performance_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = [
        row for row in _normalized_rows(rows)
        if row["_probability"] is not None and row["_target"] is not None
    ]
    probabilities = [float(row["_probability"]) for row in normalized]
    targets = [int(row["_target"]) for row in normalized]
    if not normalized:
        return {"samples": 0, "status": "NO_DATA"}
    brier = sum((p - y) ** 2 for p, y in zip(probabilities, targets)) / len(targets)
    log_loss = -sum(
        y * math.log(max(1e-8, p)) + (1 - y) * math.log(max(1e-8, 1 - p))
        for p, y in zip(probabilities, targets)
    ) / len(targets)
    profits: list[float] = []
    clv_values: list[float] = []
    priced_targets: list[int] = []
    for row in normalized:
        if row["_odds"] is None:
            continue
        priced_targets.append(int(row["_target"]))
        profits.append(float(row["_odds"]) - 1.0 if row["_target"] else -1.0)
        if row["_closing"] is not None:
            clv_values.append(float(row["_odds"]) / float(row["_closing"]) - 1.0)
    ece, reliability = _ece(probabilities, targets)
    return {
        "status": "OK",
        "samples": len(normalized),
        "priced_samples": len(profits),
        "wins": sum(targets),
        "losses": len(targets) - sum(targets),
        "hit_rate": round(sum(targets) / len(targets), 6),
        "hit_rate_ci95": _wilson(sum(targets), len(targets)),
        "brier_score": round(brier, 8),
        "log_loss": round(log_loss, 8),
        "ece": ece,
        "profit_units": round(sum(profits), 6),
        "yield": round(sum(profits) / max(1, len(profits)), 6),
        "yield_ci95": _mean_ci(profits),
        "max_drawdown_units": _drawdown(profits),
        "clv_samples": len(clv_values),
        "mean_clv": round(sum(clv_values) / max(1, len(clv_values)), 6),
        "clv_ci95": _mean_ci(clv_values),
        "positive_clv_ratio": round(sum(value > 0 for value in clv_values) / max(1, len(clv_values)), 6),
        "reliability_bins": reliability,
    }


def _odds_bucket(row: Mapping[str, Any]) -> str:
    odds = row.get("_odds")
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


def segment_report(rows: Sequence[Mapping[str, Any]], field: str, minimum: int) -> list[dict[str, Any]]:
    normalized = _normalized_rows(rows)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in normalized:
        if field == "odds_bucket":
            value = _odds_bucket(row)
        elif field == "market_league":
            value = f"{row['_market']}::{row['_league']}"
        else:
            value = str(row.get(f"_{field}", row.get(field, "UNKNOWN")) or "UNKNOWN")
        groups[value].append(row)
    output = []
    for name, group in groups.items():
        metrics = performance_metrics(group)
        samples = int(metrics.get("samples", 0))
        if samples == 0:
            continue
        yield_ci = metrics.get("yield_ci95", {})
        clv_ci = metrics.get("clv_ci95", {})
        if samples < minimum:
            status = "COLLECT_MORE_DATA"
        elif (
            metrics.get("priced_samples", 0) >= minimum
            and yield_ci.get("upper", 0.0) < 0.0
        ) or (
            metrics.get("clv_samples", 0) >= minimum
            and clv_ci.get("upper", 0.0) < 0.0
        ):
            status = "BLOCK"
        elif (
            metrics.get("priced_samples", 0) >= minimum
            and yield_ci.get("lower", -1.0) > 0.0
            and (
                metrics.get("clv_samples", 0) < minimum
                or clv_ci.get("lower", -1.0) >= 0.0
            )
        ):
            status = "VERIFIED_ADVANTAGE"
        else:
            status = "MONITOR"
        output.append({"name": name, "status": status, **metrics})
    return sorted(output, key=lambda item: (-int(item.get("samples", 0)), item["name"]))


def feature_coverage(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    fields = (
        "home_xg", "away_xg", "data_quality", "lineup_available",
        "injuries_available", "home_rest_days", "away_rest_days",
        "home_form_home", "away_form_away", "coach_change", "odds_observed_at",
    )
    total = max(1, len(rows))
    coverage = {}
    for field in fields:
        present = sum(str(row.get(field, "")).strip().lower() not in {"", "none", "nan", "null"} for row in rows)
        coverage[field] = {"present": present, "coverage": round(present / total, 6)}
    return {
        "rows": len(rows),
        "coverage": coverage,
        "recommended_next_features": [
            field for field, stats in coverage.items() if stats["coverage"] < 0.80
        ],
        "missing_features_are_never_imputed_as_real_observations": True,
    }


def build_selection_policy(report: Mapping[str, Any], minimum: int) -> dict[str, Any]:
    segments: dict[str, Any] = {}
    for field in ("market", "league", "market_league", "odds_bucket"):
        for item in report.get("segments", {}).get(field, []):
            segments[f"{field}::{item['name']}"] = {
                "status": item["status"],
                "samples": item["samples"],
                "yield": item.get("yield", 0.0),
                "mean_clv": item.get("mean_clv", 0.0),
                "brier_score": item.get("brier_score"),
            }
    global_samples = int(report.get("global", {}).get("samples", 0))
    integrity_ok = report.get("integrity", {}).get("status") != "FAIL"
    return {
        "version": 1,
        "created_at": report.get("created_at"),
        "mode": "evidence_based_abstention",
        "enforcement_ready": global_samples >= max(300, minimum * 3) and integrity_ok,
        "minimum_segment_samples": minimum,
        "minimum_data_quality": 0.65,
        "maximum_model_disagreement": 0.15,
        "maximum_odds_age_seconds": int(os.getenv("BETBOT_MAX_ODDS_AGE_SECONDS", "300")),
        "base_minimum_edge": float(os.getenv("BETBOT_QUALITY_BASE_MIN_EDGE", "0.02")),
        "unknown_segment_action": "REVIEW",
        "blocked_segment_action": "REJECT",
        "segments": segments,
        "automatic_model_promotion": False,
    }


def generate_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    minimum_segment_samples: int = 50,
) -> tuple[dict[str, Any], dict[str, Any]]:
    report = {
        "status": "CREATED",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "report_kind": "DIAGNOSTIC_ADVANTAGE_REPORT",
        "methodology": "chronological_settled_predictions_only",
        "integrity": data_integrity_audit(rows),
        "global": performance_metrics(rows),
        "segments": {
            "market": segment_report(rows, "market", minimum_segment_samples),
            "league": segment_report(rows, "league", minimum_segment_samples),
            "market_league": segment_report(rows, "market_league", minimum_segment_samples),
            "source": segment_report(rows, "source", minimum_segment_samples),
            "odds_bucket": segment_report(rows, "odds_bucket", minimum_segment_samples),
        },
        "feature_coverage": feature_coverage(rows),
        "interpretation": {
            "roi_is_not_proof_without_confidence_interval": True,
            "clv_is_primary_early_advantage_signal": True,
            "small_segments_are_never_promoted": True,
            "fewer_higher_quality_recommendations_preferred": True,
        },
        "source_history_modified": False,
        "active_model_modified": False,
    }
    return report, build_selection_policy(report, minimum_segment_samples)


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def write_report(
    training_path: str | Path,
    output_dir: str | Path,
    *,
    minimum_segment_samples: int = 50,
) -> dict[str, Any]:
    rows = load_rows(training_path)
    report, policy = generate_report(rows, minimum_segment_samples=minimum_segment_samples)
    destination = Path(output_dir)
    report_path = destination / "diagnostic_advantage_report.json"
    policy_path = destination / "quality_selection_policy.json"
    _atomic_json(report_path, report)
    _atomic_json(policy_path, policy)
    return {
        "status": report["status"],
        "rows": len(rows),
        "report": str(report_path),
        "policy": str(policy_path),
        "enforcement_ready": policy["enforcement_ready"],
        "source_history_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(get_data_dir()))
    parser.add_argument("--training", default="")
    parser.add_argument("--minimum-segment-samples", type=int, default=50)
    args = parser.parse_args()
    data_dir = Path(args.data_dir).resolve()
    training = Path(args.training).resolve() if args.training else data_dir / "quality_training.csv"
    result = write_report(
        training,
        data_dir / "quality_retraining",
        minimum_segment_samples=max(20, args.minimum_segment_samples),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
