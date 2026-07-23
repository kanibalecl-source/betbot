from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Iterable

from .domain import OddsQuote


MARKET_SCHEMA_VERSION = "volleyball.no_vig_consensus.v1"


@dataclass(frozen=True)
class MarketConsensus:
    game_id: str
    market: str
    observed_at: str
    bookmaker_count: int
    home_probability: float
    away_probability: float
    home_fair_odds: float
    away_fair_odds: float
    best_home_odds: float
    best_away_odds: float
    average_overround: float
    probability_dispersion: float

    def payload(self) -> dict:
        return {
            "market_schema": MARKET_SCHEMA_VERSION,
            "game_id": self.game_id,
            "market": self.market,
            "observed_at": self.observed_at,
            "bookmaker_count": self.bookmaker_count,
            "home_probability": self.home_probability,
            "away_probability": self.away_probability,
            "home_fair_odds": self.home_fair_odds,
            "away_fair_odds": self.away_fair_odds,
            "best_home_odds": self.best_home_odds,
            "best_away_odds": self.best_away_odds,
            "average_overround": self.average_overround,
            "probability_dispersion": self.probability_dispersion,
        }


def build_no_vig_consensus(
    quotes: Iterable[OddsQuote],
) -> MarketConsensus | None:
    rows = eligible_match_winner_quotes(quotes)
    if not rows:
        return None

    latest_observed_at = str(rows[0].observed_at)
    paired: dict[str, dict[str, OddsQuote]] = {}
    for quote in rows:
        if quote.outcome not in {"HOME", "AWAY"} or quote.odds <= 1.0:
            continue
        bookmaker_key = str(quote.bookmaker_id or quote.bookmaker).strip()
        if not bookmaker_key:
            continue
        current = paired.setdefault(bookmaker_key, {})
        prior = current.get(quote.outcome)
        if prior is None or quote.odds > prior.odds:
            current[quote.outcome] = quote

    probabilities: list[float] = []
    overrounds: list[float] = []
    home_odds: list[float] = []
    away_odds: list[float] = []
    for outcomes in paired.values():
        home = outcomes.get("HOME")
        away = outcomes.get("AWAY")
        if home is None or away is None:
            continue
        home_implied = 1.0 / home.odds
        away_implied = 1.0 / away.odds
        overround = home_implied + away_implied
        if not 0.80 <= overround <= 1.50:
            continue
        probabilities.append(home_implied / overround)
        overrounds.append(overround)
        home_odds.append(home.odds)
        away_odds.append(away.odds)
    if not probabilities:
        return None

    home_probability = min(0.99, max(0.01, float(median(probabilities))))
    away_probability = 1.0 - home_probability
    return MarketConsensus(
        game_id=str(rows[0].game_id),
        market="MATCH_WINNER",
        observed_at=latest_observed_at,
        bookmaker_count=len(probabilities),
        home_probability=round(home_probability, 8),
        away_probability=round(away_probability, 8),
        home_fair_odds=round(1.0 / home_probability, 6),
        away_fair_odds=round(1.0 / away_probability, 6),
        best_home_odds=round(max(home_odds), 6),
        best_away_odds=round(max(away_odds), 6),
        average_overround=round(float(mean(overrounds)), 8),
        probability_dispersion=round(
            float(pstdev(probabilities)) if len(probabilities) > 1 else 0.0,
            8,
        ),
    )


def eligible_match_winner_quotes(
    quotes: Iterable[OddsQuote],
) -> list[OddsQuote]:
    rows = [
        quote
        for quote in quotes
        if quote.market == "MATCH_WINNER"
        and quote.outcome in {"HOME", "AWAY"}
        and 1.0 < quote.odds <= 100.0
    ]
    if not rows:
        return []
    latest_observed_at = max(str(quote.observed_at) for quote in rows)
    rows = [
        quote for quote in rows if str(quote.observed_at) == latest_observed_at
    ]
    paired: dict[str, dict[str, OddsQuote]] = {}
    for quote in rows:
        bookmaker_key = str(quote.bookmaker_id or quote.bookmaker).strip()
        if not bookmaker_key:
            continue
        current = paired.setdefault(bookmaker_key, {})
        prior = current.get(quote.outcome)
        if prior is None or quote.odds > prior.odds:
            current[quote.outcome] = quote

    eligible: list[OddsQuote] = []
    for outcomes in paired.values():
        home = outcomes.get("HOME")
        away = outcomes.get("AWAY")
        if home is None or away is None:
            continue
        overround = (1.0 / home.odds) + (1.0 / away.odds)
        if 0.80 <= overround <= 1.50:
            eligible.extend((home, away))
    return eligible
