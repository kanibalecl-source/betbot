from __future__ import annotations

from datetime import date
from typing import Any

import requests

from api_sports_resilience_v204 import (
    ApiSportsResilientTransport,
    ResilientProviderError,
)

from .config import VolleyballSettings
from .domain import OddsQuote, VolleyballGame, utc_now


class VolleyballProviderError(ResilientProviderError):
    pass


class VolleyballRequestBudgetExhausted(VolleyballProviderError):
    pass


class ApiSportsVolleyballClient:
    def __init__(
        self,
        settings: VolleyballSettings,
        session: requests.Session | None = None,
        observer=None,
    ):
        self.settings = settings
        self.session = session or requests.Session()
        self.observer = observer
        self._transport = ApiSportsResilientTransport(
            sport="volleyball",
            settings=settings,
            session=self.session,
            observer=observer,
            provider_error_type=VolleyballProviderError,
            request_budget_error_type=VolleyballRequestBudgetExhausted,
        )

    @property
    def requests_made(self) -> int:
        return self._transport.requests_made

    @property
    def requests_remaining(self) -> int:
        return self._transport.requests_remaining

    def begin_cycle(self, limit: int | None = None) -> None:
        self._transport.begin_cycle(limit)

    def _get(self, endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        return self._transport.get(endpoint, params)

    @staticmethod
    def _remaining(response) -> int | None:
        return ApiSportsResilientTransport.response_limits(response)[1]

    def _observe(self, **payload: Any) -> None:
        if self.observer is not None:
            self.observer(payload)

    def games_for_date(self, day: date) -> list[VolleyballGame]:
        rows = self._get(
            "games",
            {"date": day.isoformat(), "timezone": self.settings.timezone},
        )
        games = [VolleyballGame.from_api(row) for row in rows]
        return [game for game in games if game.game_id and game.home_team and game.away_team]

    def odds_for_game(self, game_id: str) -> list[OddsQuote]:
        rows = self._get("odds", {"game": game_id})
        observed_at = utc_now()
        quotes: list[OddsQuote] = []
        for row in rows:
            bookmakers = row.get("bookmakers", [])
            if not isinstance(bookmakers, list):
                continue
            for bookmaker in bookmakers:
                if not isinstance(bookmaker, dict):
                    continue
                bets = bookmaker.get("bets", [])
                if not isinstance(bets, list):
                    continue
                for bet in bets:
                    if not isinstance(bet, dict):
                        continue
                    market_name = str(bet.get("name") or "")
                    normalized = market_name.lower().replace(" ", "")
                    if not any(token in normalized for token in ("home/away", "winner", "moneyline")):
                        continue
                    values = bet.get("values", [])
                    if not isinstance(values, list):
                        continue
                    for value in values:
                        if not isinstance(value, dict):
                            continue
                        outcome_raw = str(value.get("value") or "").strip().lower()
                        if outcome_raw in {"home", "1", "home team"}:
                            outcome = "HOME"
                        elif outcome_raw in {"away", "2", "away team"}:
                            outcome = "AWAY"
                        else:
                            continue
                        try:
                            price = float(value.get("odd"))
                        except (TypeError, ValueError):
                            continue
                        if price <= 1.0 or price > 100.0:
                            continue
                        quotes.append(
                            OddsQuote(
                                game_id=str(game_id),
                                bookmaker_id=str(bookmaker.get("id") or ""),
                                bookmaker=str(bookmaker.get("name") or "UNKNOWN"),
                                market="MATCH_WINNER",
                                outcome=outcome,
                                odds=price,
                                observed_at=observed_at,
                            )
                        )
        return quotes
