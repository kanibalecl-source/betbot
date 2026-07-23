from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping


def _mapping_value(row: Mapping[str, Any] | Any, key: str) -> Any:
    try:
        return row.get(key)
    except Exception:
        return None


def _first(row: Mapping[str, Any] | Any, keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = _mapping_value(row, key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() not in {"nan", "none", "null", "-"}:
            return value
    return None


def _number(value: Any) -> float | None:
    try:
        number = float(str(value).strip().replace("%", "").replace(",", "."))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def decimal_odds(value: Any) -> float | None:
    number = _number(value)
    return number if number is not None and number > 1.0 else None


def probability(value: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    if 1.0 < number < 100.0:
        number /= 100.0
    return number if 0.0 < number < 1.0 else None


def probability_odds(value: Any) -> float | None:
    prob = probability(value)
    return (1.0 / prob) if prob is not None else None


def _odds_or_probability(
    row: Mapping[str, Any] | Any,
    odds_keys: tuple[str, ...],
    probability_keys: tuple[str, ...],
) -> float | None:
    odds = decimal_odds(_first(row, odds_keys))
    if odds is not None:
        return odds
    return probability_odds(_first(row, probability_keys))


@dataclass(frozen=True)
class OddsSnapshot:
    model: float | None
    bot: float | None
    bookmaker: float | None
    closing: float | None
    value_percent: float | None
    clv_percent: float | None
    bookmaker_name: str
    observed_at: str


def extract_odds_snapshot(row: Mapping[str, Any] | Any) -> OddsSnapshot:
    model = _odds_or_probability(
        row,
        ("kurs_model", "model_odds", "fair_odds_model"),
        ("prawd_model", "verified_model_probability", "model_probability", "model_prob"),
    )
    bot = _odds_or_probability(
        row,
        ("kurs_bota", "bot_odds", "fair_odds_final", "fair_odds", "ai_odds"),
        ("prawd_final", "final_probability", "final_prob", "calibrated_probability"),
    )
    bookmaker = decimal_odds(
        _first(row, ("kurs_buk", "bookmaker_odds", "book_odds", "odds"))
    )
    closing = decimal_odds(
        _first(row, ("closing_odds", "close_odds", "closing_line_odds", "odds_close"))
    )

    value_percent = None
    if bookmaker is not None and bot is not None:
        value_percent = ((bookmaker / bot) - 1.0) * 100.0

    clv_percent = _number(_first(row, ("clv_percent", "clv")))
    if clv_percent is None and bookmaker is not None and closing is not None:
        clv_percent = ((bookmaker / closing) - 1.0) * 100.0

    bookmaker_name = str(
        _first(row, ("bookmaker", "margin_bookmaker", "bookmaker_name")) or ""
    ).strip()
    observed_at = str(
        _first(row, ("odds_observed_at", "observed_at", "decision_at")) or ""
    ).strip()
    return OddsSnapshot(
        model=model,
        bot=bot,
        bookmaker=bookmaker,
        closing=closing,
        value_percent=value_percent,
        clv_percent=clv_percent,
        bookmaker_name=bookmaker_name,
        observed_at=observed_at,
    )


def format_odds(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "-"


def format_percent(value: float | None, *, signed: bool = True) -> str:
    if value is None:
        return "-"
    return f"{value:+.1f}%" if signed else f"{value:.1f}%"


def format_closing_clv(snapshot: OddsSnapshot) -> str:
    closing = format_odds(snapshot.closing)
    clv = format_percent(snapshot.clv_percent)
    if snapshot.closing is None and snapshot.clv_percent is None:
        return "oczekuje"
    if snapshot.clv_percent is None:
        return closing
    if snapshot.closing is None:
        return f"CLV {clv}"
    return f"{closing} / {clv}"
