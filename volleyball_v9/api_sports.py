from __future__ import annotations

from datetime import date
import hashlib
import json
import time
from typing import Any

import requests

from .config import VolleyballSettings
from .domain import OddsQuote, VolleyballGame, utc_now


class VolleyballProviderError(RuntimeError):
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

    def _get(self, endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        params_json = json.dumps(params, sort_keys=True, separators=(",", ":"))
        call_id = hashlib.sha256(
            f"{endpoint}|{params_json}|{time.time_ns()}".encode("utf-8")
        ).hexdigest()
        started = time.monotonic()
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
                status_code = int(getattr(response, "status_code", 200))
                if status_code == 429 or status_code >= 500:
                    raise VolleyballProviderError(f"retryable HTTP {status_code}")
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise VolleyballProviderError(
                        "API-Sports returned a non-object response"
                    )
                errors = payload.get("errors")
                if errors:
                    raise VolleyballProviderError(f"API-Sports errors: {errors}")
                rows = payload.get("response", [])
                if not isinstance(rows, list):
                    raise VolleyballProviderError(
                        "API-Sports response field is not a list"
                    )
                clean_rows = [row for row in rows if isinstance(row, dict)]
                self._observe(
                    call_id=f"{call_id}:{attempt}",
                    endpoint=endpoint,
                    params_json=params_json,
                    attempt=attempt,
                    status="SUCCESS",
                    http_status=status_code,
                    rows=len(clean_rows),
                    duration_ms=int((time.monotonic() - started) * 1000),
                    remaining=self._remaining(response),
                )
                return clean_rows
            except Exception as exc:
                last_error = exc
                status_code = int(getattr(response, "status_code", 0) or 0)
                retryable = status_code == 429 or status_code >= 500 or status_code == 0
                if attempt < self.settings.retry_attempts and retryable:
                    self._observe(
                        call_id=f"{call_id}:{attempt}",
                        endpoint=endpoint,
                        params_json=params_json,
                        attempt=attempt,
                        status="RETRY",
                        http_status=status_code,
                        rows=0,
                        duration_ms=int((time.monotonic() - started) * 1000),
                        remaining=self._remaining(response),
                        error_type=type(exc).__name__,
                        error=str(exc)[:500],
                    )
                    time.sleep(
                        self.settings.retry_backoff_seconds * (2 ** (attempt - 1))
                    )
                    continue
                self._observe(
                    call_id=f"{call_id}:{attempt}",
                    endpoint=endpoint,
                    params_json=params_json,
                    attempt=attempt,
                    status="FAILED",
                    http_status=status_code,
                    rows=0,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    remaining=self._remaining(response),
                    error_type=type(exc).__name__,
                    error=str(exc)[:500],
                )
                break
        raise VolleyballProviderError(str(last_error or "provider request failed"))

    @staticmethod
    def _remaining(response) -> int | None:
        if response is None:
            return None
        headers = getattr(response, "headers", {}) or {}
        for name in ("x-ratelimit-requests-remaining", "X-RateLimit-Remaining"):
            try:
                if name in headers:
                    return int(headers[name])
            except (TypeError, ValueError):
                return None
        return None

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
                        if price <= 1.0:
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
