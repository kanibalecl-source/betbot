from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable

import requests

from .config import BasketballSettings
from .domain import BasketballGame, BasketballOddsQuote, utc_now


class BasketballProviderError(RuntimeError):
    pass


class BasketballProviderUnavailable(BasketballProviderError):
    pass


Observer = Callable[..., None]


class ApiSportsBasketballClient:
    def __init__(
        self,
        settings: BasketballSettings,
        session: requests.Session | None = None,
        observer: Observer | None = None,
    ) -> None:
        self.settings = settings
        self.session = session or requests.Session()
        self.observer = observer

    def _observe(self, endpoint: str, **kwargs: Any) -> None:
        if self.observer:
            self.observer("api_sports_basketball", endpoint, **kwargs)

    def _get(
        self, endpoint: str, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        params_json = json.dumps(params, sort_keys=True, separators=(",", ":"))
        call_id = hashlib.sha256(
            f"{endpoint}|{params_json}|{time.time_ns()}".encode()
        ).hexdigest()[:20]
        last_error: Exception | None = None
        for attempt in range(1, self.settings.retry_attempts + 1):
            response = None
            try:
                response = self.session.get(
                    f"{self.settings.api_base_url}/{endpoint.lstrip('/')}",
                    params=params,
                    headers={"x-apisports-key": self.settings.api_key},
                    timeout=self.settings.request_timeout_seconds,
                )
                status = int(getattr(response, "status_code", 200))
                if status in {401, 403, 404}:
                    error_type = (
                        "AUTH" if status in {401, 403}
                        else "ENDPOINT_UNAVAILABLE"
                    )
                    self._observe(
                        endpoint, success=False, status_code=status,
                        error_type=error_type, call_id=call_id,
                    )
                    raise BasketballProviderUnavailable(
                        f"non-retryable HTTP {status}"
                    )
                if status == 429 or status >= 500:
                    raise BasketballProviderError(
                        f"retryable HTTP {status}"
                    )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise BasketballProviderError(
                        "provider returned a non-object response"
                    )
                if payload.get("errors"):
                    raise BasketballProviderError(
                        f"provider errors: {payload.get('errors')}"
                    )
                rows = payload.get("response", [])
                if not isinstance(rows, list):
                    raise BasketballProviderError(
                        "provider response field is not a list"
                    )
                rows = [row for row in rows if isinstance(row, dict)]
                self._observe(
                    endpoint, success=True, status_code=status,
                    rows_received=len(rows), call_id=call_id,
                )
                return rows
            except BasketballProviderUnavailable:
                raise
            except Exception as exc:
                last_error = exc
                status = getattr(response, "status_code", None)
                if attempt >= self.settings.retry_attempts:
                    self._observe(
                        endpoint, success=False, status_code=status,
                        error_type=type(exc).__name__, call_id=call_id,
                    )
                    break
                time.sleep(
                    self.settings.retry_backoff_seconds * (2 ** (attempt - 1))
                )
        raise BasketballProviderError(
            f"{endpoint} failed: {type(last_error).__name__}"
        )

    def games_for_date(self, value: str) -> list[BasketballGame]:
        rows = self._get(
            "games", {"date": value, "timezone": self.settings.timezone}
        )
        return [BasketballGame.from_api(row) for row in rows]

    @staticmethod
    def _market_name(name: str) -> str:
        normalized = " ".join(name.lower().split())
        if any(token in normalized for token in ("winner", "moneyline")):
            return "MONEYLINE"
        if any(token in normalized for token in ("handicap", "spread")):
            return "POINT_SPREAD"
        if any(token in normalized for token in ("total", "over/under")):
            return "TOTAL_POINTS"
        return ""

    @staticmethod
    def _parse_value(raw: Any) -> tuple[str, float | None]:
        text = " ".join(str(raw or "").strip().split())
        line = None
        for part in reversed(text.replace("(", " ").replace(")", " ").split()):
            try:
                line = float(part)
                break
            except ValueError:
                continue
        lowered = text.lower()
        if lowered.startswith("home") or lowered in {"1", "team 1"}:
            outcome = "HOME"
        elif lowered.startswith("away") or lowered in {"2", "team 2"}:
            outcome = "AWAY"
        elif lowered.startswith("over"):
            outcome = "OVER"
        elif lowered.startswith("under"):
            outcome = "UNDER"
        else:
            outcome = text.upper()
        return outcome, line

    def odds_for_game(self, game_id: str) -> list[BasketballOddsQuote]:
        rows = self._get("odds", {"game": game_id})
        observed_at = utc_now()
        output: list[BasketballOddsQuote] = []
        for row in rows:
            bookmakers = row.get("bookmakers")
            bookmakers = bookmakers if isinstance(bookmakers, list) else []
            for bookmaker in bookmakers:
                if not isinstance(bookmaker, dict):
                    continue
                bets = bookmaker.get("bets")
                bets = bets if isinstance(bets, list) else []
                for bet in bets:
                    if not isinstance(bet, dict):
                        continue
                    market = self._market_name(
                        str(bet.get("name") or bet.get("id") or "")
                    )
                    if not market:
                        continue
                    values = bet.get("values")
                    values = values if isinstance(values, list) else []
                    for value in values:
                        if not isinstance(value, dict):
                            continue
                        try:
                            odds = float(
                                value.get("odd") or value.get("odds")
                            )
                        except (TypeError, ValueError):
                            continue
                        outcome, line = self._parse_value(
                            value.get("value") or value.get("name")
                        )
                        if odds <= 1.0 or not outcome:
                            continue
                        output.append(
                            BasketballOddsQuote(
                                game_id=str(game_id),
                                bookmaker_id=str(bookmaker.get("id") or ""),
                                bookmaker=str(
                                    bookmaker.get("name") or "UNKNOWN"
                                ),
                                market=market,
                                outcome=outcome,
                                line=line,
                                odds=odds,
                                observed_at=observed_at,
                            )
                        )
        return output

