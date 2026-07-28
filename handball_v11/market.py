from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from market_data_integrity_v13 import admit_market_quotes, build_market_consensus
from .domain import OddsQuote


MARKET_SCHEMA_VERSION = "handball.market_integrity_consensus.v13"


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
    source_bookmakers: tuple[str, ...] = ()

    def payload(self) -> dict:
        multi_book = self.bookmaker_count >= 2
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
            "source_bookmakers": list(self.source_bookmakers),
            "market_quality_tier": (
                "AB_MULTI_BOOK" if multi_book else "C_SINGLE_BOOK_SHADOW"
            ),
            "shadow_observation_only": not multi_book,
            "training_eligible": multi_book,
            "pick_eligible": multi_book,
            "promotion_eligible": multi_book,
            "de_vig_applied": True,
            "complete_market_required": True,
        }


def build_no_vig_consensus(
    quotes: Iterable[OddsQuote],
) -> MarketConsensus | None:
    result = build_market_consensus(
        list(quotes),
        sport="handball",
        market="MATCH_WINNER_NO_DRAW",
        required_outcomes=("HOME", "AWAY"),
        minimum_bookmakers=1,
    )
    if result.get("status") != "PASS":
        return None
    accepted = result["accepted_quotes"]
    return MarketConsensus(
        game_id=str(accepted[0].game_id),
        market="MATCH_WINNER_NO_DRAW",
        observed_at=str(result["observed_at"]),
        bookmaker_count=int(result["bookmaker_count"]),
        home_probability=round(float(result["probabilities"]["HOME"]), 8),
        away_probability=round(float(result["probabilities"]["AWAY"]), 8),
        home_fair_odds=round(float(result["fair_odds"]["HOME"]), 6),
        away_fair_odds=round(float(result["fair_odds"]["AWAY"]), 6),
        best_home_odds=round(float(result["best_odds"]["HOME"]), 6),
        best_away_odds=round(float(result["best_odds"]["AWAY"]), 6),
        average_overround=round(float(result["average_overround"]), 8),
        probability_dispersion=round(float(result["probability_dispersion"]), 8),
        source_bookmakers=tuple(
            sorted(
                {
                    str(item.bookmaker_id or item.bookmaker).strip()
                    for item in accepted
                    if str(item.bookmaker_id or item.bookmaker).strip()
                }
            )
        ),
    )


def eligible_match_winner_quotes(
    quotes: Iterable[OddsQuote],
) -> list[OddsQuote]:
    result = admit_market_quotes(
        list(quotes),
        sport="handball",
        market="MATCH_WINNER_NO_DRAW",
        required_outcomes=("HOME", "AWAY"),
        minimum_bookmakers=1,
    )
    return list(result.get("accepted_quotes", []))

