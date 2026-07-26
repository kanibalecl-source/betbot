"""Shared safety contracts for sport-specific BetBot v12 pipelines.

The module contains no provider calls and never mutates source history.  It
provides deterministic policies for sport isolation, league-quality grading,
odds-timeline labelling, calibration diagnostics and promotion readiness.
Each sport keeps its own model, storage and registry; only the rules are shared.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "betbot.multisport_quality.v12"
SUPPORTED_SPORTS = ("football", "volleyball", "handball")


@dataclass(frozen=True)
class SportQualityPolicy:
    sport: str
    candidate_minimum_rows: int
    promotion_minimum_rows: int
    out_of_time_minimum_rows: int
    live_shadow_minimum_rows: int
    minimum_positive_windows: int
    minimum_settlement_coverage: float
    minimum_closing_odds_coverage: float
    maximum_ece: float
    maximum_psi: float
    minimum_grade_ab_share: float


POLICIES: dict[str, SportQualityPolicy] = {
    "football": SportQualityPolicy(
        "football", 300, 1000, 300, 250, 3, 0.97, 0.85, 0.055, 0.20, 0.80
    ),
    "volleyball": SportQualityPolicy(
        "volleyball", 250, 750, 240, 180, 3, 0.97, 0.80, 0.065, 0.22, 0.75
    ),
    "handball": SportQualityPolicy(
        "handball", 300, 850, 260, 200, 3, 0.97, 0.80, 0.065, 0.22, 0.75
    ),
}


def policy_for(sport: str) -> SportQualityPolicy:
    key = str(sport or "").strip().lower()
    if key not in POLICIES:
        raise ValueError(f"unsupported sport: {sport!r}")
    return POLICIES[key]


def parse_utc(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def odds_snapshot_stage(kickoff: Any, observed_at: Any) -> str:
    """Return a stable pre-event bucket; post-event quotes are rejected."""
    event = parse_utc(kickoff)
    observed = parse_utc(observed_at)
    if event is None or observed is None:
        return "INVALID_TIME"
    minutes = (event - observed).total_seconds() / 60.0
    if minutes <= 0:
        return "POST_KICKOFF_REJECT"
    if minutes > 24 * 60:
        return "OPENING"
    if minutes > 12 * 60:
        return "T_MINUS_24H"
    if minutes > 6 * 60:
        return "T_MINUS_12H"
    if minutes > 3 * 60:
        return "T_MINUS_6H"
    if minutes > 60:
        return "T_MINUS_3H"
    if minutes > 15:
        return "T_MINUS_60M"
    return "CLOSING"


def calibration_report(
    probabilities: Sequence[float],
    targets: Sequence[int],
    *,
    bins: int = 10,
) -> dict[str, Any]:
    if len(probabilities) != len(targets) or not probabilities:
        return {
            "status": "WAITING_SAMPLE",
            "samples": 0,
            "brier": None,
            "log_loss": None,
            "ece": None,
            "bins": [],
        }
    bucketed: dict[int, list[tuple[float, int]]] = defaultdict(list)
    brier: list[float] = []
    log_loss: list[float] = []
    for raw_probability, raw_target in zip(probabilities, targets):
        probability = min(1.0 - 1e-12, max(1e-12, float(raw_probability)))
        target = 1 if int(raw_target) else 0
        bucketed[min(bins - 1, int(probability * bins))].append(
            (probability, target)
        )
        brier.append((probability - target) ** 2)
        log_loss.append(
            -(target * math.log(probability) + (1 - target) * math.log(1 - probability))
        )
    total = len(probabilities)
    rows = []
    ece = 0.0
    for bucket in range(bins):
        values = bucketed.get(bucket, [])
        if not values:
            continue
        predicted = sum(item[0] for item in values) / len(values)
        observed = sum(item[1] for item in values) / len(values)
        error = abs(predicted - observed)
        ece += len(values) / total * error
        rows.append(
            {
                "bucket": bucket,
                "samples": len(values),
                "predicted": round(predicted, 8),
                "observed": round(observed, 8),
                "absolute_error": round(error, 8),
            }
        )
    return {
        "status": "READY",
        "samples": total,
        "brier": round(sum(brier) / total, 10),
        "log_loss": round(sum(log_loss) / total, 10),
        "ece": round(ece, 10),
        "bins": rows,
    }


def grade_leagues(
    rows: Iterable[Mapping[str, Any]],
    *,
    sport: str,
) -> dict[str, dict[str, Any]]:
    """Grade data reliability, never sporting strength or profitability."""
    policy = policy_for(sport)
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if str(row.get("sport") or sport).strip().lower() != sport:
            continue
        grouped[str(row.get("league_id") or row.get("league") or "UNKNOWN")].append(row)
    result: dict[str, dict[str, Any]] = {}
    for league, league_rows in sorted(grouped.items()):
        samples = len(league_rows)
        settled = sum(bool(row.get("settled") or row.get("result")) for row in league_rows)
        closing = sum(
            row.get("closing_odds") not in (None, "", 0, 0.0)
            for row in league_rows
        )
        identified = sum(
            bool(row.get("fixture_id") or row.get("game_id"))
            and bool(row.get("home_team_id"))
            and bool(row.get("away_team_id"))
            for row in league_rows
        )
        settlement_coverage = settled / samples if samples else 0.0
        closing_coverage = closing / samples if samples else 0.0
        identity_coverage = identified / samples if samples else 0.0
        if (
            samples >= max(100, policy.out_of_time_minimum_rows // 2)
            and settlement_coverage >= 0.98
            and closing_coverage >= 0.85
            and identity_coverage >= 0.99
        ):
            grade = "A"
        elif (
            samples >= 50
            and settlement_coverage >= 0.95
            and closing_coverage >= 0.65
            and identity_coverage >= 0.97
        ):
            grade = "B"
        elif samples >= 20 and settlement_coverage >= 0.85 and identity_coverage >= 0.90:
            grade = "C"
        else:
            grade = "QUARANTINE"
        result[league] = {
            "sport": sport,
            "grade": grade,
            "samples": samples,
            "settlement_coverage": round(settlement_coverage, 6),
            "closing_odds_coverage": round(closing_coverage, 6),
            "identity_coverage": round(identity_coverage, 6),
            "training_allowed": grade in {"A", "B"},
            "publication_allowed": grade == "A",
        }
    return result


def audit_sport_isolation(
    datasets: Mapping[str, Iterable[Mapping[str, Any]]],
) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    identities: dict[str, str] = {}
    for expected, raw_rows in datasets.items():
        expected_key = str(expected).strip().lower()
        if expected_key not in SUPPORTED_SPORTS:
            violations.append({"dataset": expected_key, "reason": "unsupported_dataset"})
            continue
        for row in raw_rows:
            observed = str(row.get("sport") or expected_key).strip().lower()
            if observed != expected_key:
                violations.append(
                    {
                        "dataset": expected_key,
                        "observed": observed,
                        "reason": "sport_dataset_contamination",
                    }
                )
            fixture = str(row.get("fixture_id") or row.get("game_id") or "").strip()
            if fixture:
                composite = f"{expected_key}:{fixture}"
                prior = identities.get(composite)
                signature = "|".join(
                    (
                        str(row.get("home_team_id") or ""),
                        str(row.get("away_team_id") or ""),
                        str(row.get("scheduled_at") or row.get("kickoff") or ""),
                    )
                )
                if prior is not None and prior != signature:
                    violations.append(
                        {
                            "dataset": expected_key,
                            "fixture": fixture,
                            "reason": "conflicting_fixture_identity",
                        }
                    )
                identities[composite] = signature
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if not violations else "FAIL_CLOSED",
        "isolated": not violations,
        "violations": violations,
    }


def promotion_readiness(
    *,
    sport: str,
    training_rows: int,
    out_of_time_rows: int,
    live_shadow_rows: int,
    positive_windows: int,
    settlement_coverage: float,
    closing_odds_coverage: float,
    challenger_ece: float,
    probability_psi: float,
    brier_ci_low: float,
    log_loss_ci_low: float,
    grade_ab_share: float,
    segment_stable: bool,
) -> dict[str, Any]:
    policy = policy_for(sport)
    gates = {
        "promotion_minimum_rows": training_rows >= policy.promotion_minimum_rows,
        "out_of_time_minimum_rows": out_of_time_rows >= policy.out_of_time_minimum_rows,
        "live_shadow_minimum_rows": live_shadow_rows >= policy.live_shadow_minimum_rows,
        "positive_windows": positive_windows >= policy.minimum_positive_windows,
        "settlement_coverage": settlement_coverage >= policy.minimum_settlement_coverage,
        "closing_odds_coverage": closing_odds_coverage >= policy.minimum_closing_odds_coverage,
        "calibration": challenger_ece <= policy.maximum_ece,
        "probability_drift": probability_psi <= policy.maximum_psi,
        "brier_ci_positive": brier_ci_low > 0.0,
        "log_loss_ci_positive": log_loss_ci_low > 0.0,
        "grade_ab_share": grade_ab_share >= policy.minimum_grade_ab_share,
        "segment_stability": bool(segment_stable),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "sport": sport,
        "policy": asdict(policy),
        "gates": gates,
        "ready": all(gates.values()),
        "decision": "PROMOTION_ALLOWED" if all(gates.values()) else "KEEP_CHAMPION",
    }
