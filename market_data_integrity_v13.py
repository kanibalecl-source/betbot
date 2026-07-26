"""Fail-closed market-data admission and consensus for all BetBot sports.

The module is deterministic and provider agnostic.  It never fetches data,
modifies source history, promotes a model or enables financial execution.
Only complete bookmaker markets survive admission.  Consensus is calculated
from no-vig probabilities and quotes inconsistent with the market median are
quarantined before a best executable price is selected.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median, pstdev
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "betbot.market_data_integrity.v13"


def _value(row: Any, key: str) -> Any:
    if isinstance(row, Mapping):
        return row.get(key)
    return getattr(row, key, None)


def _token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _decimal(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and 1.0 < number <= 100.0 else None


def _parse_utc(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class IntegrityPolicy:
    sport: str
    minimum_bookmakers: int
    maximum_quote_skew_seconds: int
    minimum_overround: float
    maximum_overround: float
    maximum_probability_dispersion: float
    maximum_probability_deviation: float
    outlier_mad_multiplier: float


def policy_for(sport: str, outcomes: int = 2) -> IntegrityPolicy:
    key = str(sport or "").strip().lower()
    if key not in {"football", "volleyball", "handball"}:
        raise ValueError(f"unsupported sport: {sport!r}")
    prefix = f"BETBOT_V13_{key.upper()}"
    defaults = {"football": 2, "volleyball": 2, "handball": 2}
    return IntegrityPolicy(
        sport=key,
        minimum_bookmakers=max(
            1, int(os.getenv(f"{prefix}_MIN_BOOKMAKERS", str(defaults[key])))
        ),
        maximum_quote_skew_seconds=max(
            1, int(os.getenv(f"{prefix}_MAX_QUOTE_SKEW_SECONDS", "180"))
        ),
        minimum_overround=float(
            os.getenv(f"{prefix}_MIN_OVERROUND", "0.80" if outcomes == 2 else "0.85")
        ),
        maximum_overround=float(
            os.getenv(f"{prefix}_MAX_OVERROUND", "1.35" if outcomes == 2 else "1.45")
        ),
        maximum_probability_dispersion=float(
            os.getenv(f"{prefix}_MAX_PROBABILITY_DISPERSION", "0.075")
        ),
        maximum_probability_deviation=float(
            os.getenv(f"{prefix}_MAX_PROBABILITY_DEVIATION", "0.12")
        ),
        outlier_mad_multiplier=float(
            os.getenv(f"{prefix}_OUTLIER_MAD_MULTIPLIER", "3.5")
        ),
    )


def admit_market_quotes(
    quotes: Iterable[Any],
    *,
    sport: str,
    market: str,
    required_outcomes: Sequence[str],
    bookmaker_allowlist: Iterable[str] | None = None,
    minimum_bookmakers: int | None = None,
) -> dict[str, Any]:
    """Return complete, time-aligned and non-outlying bookmaker markets."""
    rows = list(quotes)
    outcomes = tuple(str(item).strip().upper() for item in required_outcomes)
    policy = policy_for(sport, len(outcomes))
    required = set(outcomes)
    allowed = (
        {_token(item) for item in bookmaker_allowlist if _token(item)}
        if bookmaker_allowlist is not None
        else None
    )
    rejected: Counter[str] = Counter()
    parsed_rows: list[tuple[Any, str, str, float, datetime]] = []
    for row in rows:
        row_market = str(_value(row, "market") or market).strip().upper()
        outcome = str(_value(row, "outcome") or "").strip().upper()
        bookmaker = str(_value(row, "bookmaker") or "").strip()
        bookmaker_id = str(_value(row, "bookmaker_id") or "").strip()
        bookmaker_key = bookmaker_id or _token(bookmaker)
        odds = _decimal(_value(row, "odds"))
        observed = _parse_utc(_value(row, "observed_at"))
        if row_market != str(market).strip().upper():
            rejected["wrong_market"] += 1
        elif outcome not in required:
            rejected["wrong_outcome"] += 1
        elif not bookmaker or not bookmaker_key:
            rejected["missing_bookmaker"] += 1
        elif allowed is not None and _token(bookmaker) not in allowed:
            rejected["bookmaker_not_allowed"] += 1
        elif odds is None:
            rejected["invalid_odds"] += 1
        elif observed is None:
            rejected["invalid_observed_at"] += 1
        else:
            parsed_rows.append((row, bookmaker_key, outcome, odds, observed))

    if not parsed_rows:
        return {
            "schema_version": SCHEMA_VERSION,
            "sport": sport,
            "market": market,
            "status": "QUARANTINED",
            "reason": "NO_VALID_QUOTES",
            "accepted_quotes": [],
            "accepted_bookmakers": [],
            "rejected": dict(rejected),
        }

    latest = max(item[4] for item in parsed_rows)
    aligned = []
    for item in parsed_rows:
        if (latest - item[4]).total_seconds() > policy.maximum_quote_skew_seconds:
            rejected["stale_relative_quote"] += 1
        else:
            aligned.append(item)

    paired: dict[str, dict[str, tuple[Any, float, datetime]]] = {}
    for row, bookmaker_key, outcome, odds, observed in aligned:
        current = paired.setdefault(bookmaker_key, {})
        previous = current.get(outcome)
        if previous is None or observed > previous[2]:
            current[outcome] = (row, odds, observed)

    complete: list[dict[str, Any]] = []
    for bookmaker_key, values in paired.items():
        if set(values) != required:
            rejected["incomplete_bookmaker_market"] += 1
            continue
        implied = [1.0 / values[outcome][1] for outcome in outcomes]
        overround = sum(implied)
        if not policy.minimum_overround <= overround <= policy.maximum_overround:
            rejected["implausible_overround"] += 1
            continue
        probabilities = {
            outcome: implied[index] / overround
            for index, outcome in enumerate(outcomes)
        }
        complete.append(
            {
                "bookmaker_key": bookmaker_key,
                "values": values,
                "probabilities": probabilities,
                "overround": overround,
            }
        )

    if not complete:
        return {
            "schema_version": SCHEMA_VERSION,
            "sport": sport,
            "market": market,
            "status": "QUARANTINED",
            "reason": "NO_COMPLETE_BOOKMAKER_MARKET",
            "accepted_quotes": [],
            "accepted_bookmakers": [],
            "rejected": dict(rejected),
        }

    probability_medians = {
        outcome: median(item["probabilities"][outcome] for item in complete)
        for outcome in outcomes
    }
    deviations = [
        max(
            abs(item["probabilities"][outcome] - probability_medians[outcome])
            for outcome in outcomes
        )
        for item in complete
    ]
    deviation_median = median(deviations)
    mad = median(abs(value - deviation_median) for value in deviations)
    dynamic_limit = max(
        policy.maximum_probability_deviation,
        deviation_median + policy.outlier_mad_multiplier * mad,
    )

    accepted_groups = []
    for item, deviation in zip(complete, deviations):
        # With fewer than three complete books there is not enough evidence to
        # label one an outlier; the minimum-bookmaker gate still applies.
        if len(complete) >= 3 and deviation > dynamic_limit:
            rejected["probability_outlier"] += 1
        else:
            accepted_groups.append(item)

    minimum = policy.minimum_bookmakers if minimum_bookmakers is None else max(
        1, int(minimum_bookmakers)
    )
    accepted_quotes = []
    for item in accepted_groups:
        for outcome in outcomes:
            accepted_quotes.append(item["values"][outcome][0])

    status = "PASS" if len(accepted_groups) >= minimum else "WAITING_CONSENSUS"
    return {
        "schema_version": SCHEMA_VERSION,
        "sport": sport,
        "market": market,
        "status": status,
        "reason": (
            "ACCEPTED"
            if status == "PASS"
            else f"MINIMUM_BOOKMAKERS_{minimum}_NOT_MET"
        ),
        "observed_at": latest.isoformat(),
        "accepted_quotes": accepted_quotes,
        "accepted_bookmakers": [
            item["bookmaker_key"] for item in accepted_groups
        ],
        "bookmaker_probabilities": [
            item["probabilities"] for item in accepted_groups
        ],
        "overrounds": [item["overround"] for item in accepted_groups],
        "minimum_bookmakers": minimum,
        "rejected": dict(rejected),
    }


def build_market_consensus(
    quotes: Iterable[Any],
    *,
    sport: str,
    market: str,
    required_outcomes: Sequence[str],
    bookmaker_allowlist: Iterable[str] | None = None,
    minimum_bookmakers: int | None = None,
) -> dict[str, Any]:
    admission = admit_market_quotes(
        quotes,
        sport=sport,
        market=market,
        required_outcomes=required_outcomes,
        bookmaker_allowlist=bookmaker_allowlist,
        minimum_bookmakers=minimum_bookmakers,
    )
    if admission["status"] != "PASS":
        return admission

    outcomes = tuple(str(item).strip().upper() for item in required_outcomes)
    probabilities = {
        outcome: median(
            item[outcome] for item in admission["bookmaker_probabilities"]
        )
        for outcome in outcomes
    }
    total = sum(probabilities.values())
    probabilities = {key: value / total for key, value in probabilities.items()}
    accepted_quotes = admission["accepted_quotes"]
    best_odds: dict[str, float] = {}
    best_bookmakers: dict[str, str] = {}
    best_bookmaker_ids: dict[str, str] = {}
    by_bookmaker: dict[str, dict[str, float]] = {}
    for row in accepted_quotes:
        outcome = str(_value(row, "outcome")).strip().upper()
        odds = float(_value(row, "odds"))
        bookmaker = str(_value(row, "bookmaker") or "").strip()
        bookmaker_id = str(_value(row, "bookmaker_id") or "").strip()
        by_bookmaker.setdefault(bookmaker, {})[outcome] = odds
        if outcome not in best_odds or odds > best_odds[outcome]:
            best_odds[outcome] = odds
            best_bookmakers[outcome] = bookmaker
            best_bookmaker_ids[outcome] = bookmaker_id

    per_outcome_dispersion = {
        outcome: (
            pstdev(
                item[outcome]
                for item in admission["bookmaker_probabilities"]
            )
            if len(admission["bookmaker_probabilities"]) > 1
            else 0.0
        )
        for outcome in outcomes
    }
    dispersion = max(per_outcome_dispersion.values(), default=0.0)
    policy = policy_for(sport, len(outcomes))
    status = (
        "PASS"
        if dispersion <= policy.maximum_probability_dispersion
        else "QUARANTINED"
    )
    reason = "ACCEPTED" if status == "PASS" else "EXCESSIVE_MARKET_DISPERSION"
    serializable = {
        "schema_version": SCHEMA_VERSION,
        "sport": sport,
        "market": market,
        "status": status,
        "reason": reason,
        "observed_at": admission["observed_at"],
        "bookmaker_count": len(admission["accepted_bookmakers"]),
        "accepted_bookmakers": admission["accepted_bookmakers"],
        "probabilities": probabilities,
        "fair_odds": {key: 1.0 / value for key, value in probabilities.items()},
        "best_odds": best_odds,
        "best_bookmakers": best_bookmakers,
        "best_bookmaker_ids": best_bookmaker_ids,
        "by_bookmaker": by_bookmaker,
        "average_overround": sum(admission["overrounds"])
        / len(admission["overrounds"]),
        "probability_dispersion": dispersion,
        "per_outcome_dispersion": per_outcome_dispersion,
        "rejected": admission["rejected"],
        "minimum_bookmakers": admission["minimum_bookmakers"],
    }
    serializable["consensus_id"] = hashlib.sha256(
        _canonical(serializable).encode("utf-8")
    ).hexdigest()
    return {**serializable, "accepted_quotes": accepted_quotes}
