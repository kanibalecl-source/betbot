from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable

import requests

from .config import BasketballSettings
from .domain import BasketballGame, BasketballOddsQuote, utc_now


class BasketballProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        category: str = "PROVIDER",
        status_code: int | None = None,
        retry_after_seconds: int | None = None,
        quota_limit: int | None = None,
        quota_remaining: int | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.quota_limit = quota_limit
        self.quota_remaining = quota_remaining


class BasketballProviderUnavailable(BasketballProviderError):
    pass


class BasketballRequestBudgetExhausted(BasketballProviderError):
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
        self._cycle_request_limit = settings.maximum_requests_per_cycle
        self._cycle_requests_made = 0
        self._last_request_at = 0.0

    @property
    def requests_made(self) -> int:
        return self._cycle_requests_made

    @property
    def requests_remaining(self) -> int:
        return max(0, self._cycle_request_limit - self._cycle_requests_made)

    def begin_cycle(self, limit: int | None = None) -> None:
        self._cycle_request_limit = int(
            limit or self.settings.maximum_requests_per_cycle
        )
        self._cycle_requests_made = 0

    @staticmethod
    def _header_integer(headers: Any, *names: str) -> int | None:
        for name in names:
            try:
                raw = headers.get(name)
            except AttributeError:
                raw = None
            if raw in (None, ""):
                continue
            try:
                return int(float(str(raw).strip()))
            except (TypeError, ValueError):
                continue
        return None

    @classmethod
    def _response_limits(
        cls, response: Any
    ) -> tuple[int | None, int | None, int | None]:
        headers = getattr(response, "headers", {}) or {}
        limit = cls._header_integer(
            headers,
            "x-ratelimit-requests-limit",
            "X-RateLimit-Requests-Limit",
            "x-ratelimit-limit",
            "X-RateLimit-Limit",
        )
        remaining = cls._header_integer(
            headers,
            "x-ratelimit-requests-remaining",
            "X-RateLimit-Requests-Remaining",
            "x-ratelimit-remaining",
            "X-RateLimit-Remaining",
        )
        retry_after = cls._header_integer(
            headers, "retry-after", "Retry-After"
        )
        return limit, remaining, retry_after

    @staticmethod
    def _provider_error_category(raw: Any) -> str:
        text = json.dumps(raw, ensure_ascii=True, default=str).lower()
        if any(token in text for token in ("api key", "authentication", "unauthor")):
            return "AUTH"
        if any(token in text for token in ("quota", "daily limit", "requests limit")):
            return "QUOTA"
        if any(token in text for token in ("rate limit", "too many request")):
            return "RATE_LIMIT"
        if any(token in text for token in ("plan", "subscription", "access")):
            return "ENTITLEMENT"
        if any(token in text for token in ("season", "coverage", "not available")):
            return "COVERAGE"
        return "PROVIDER_RESPONSE"

    def _consume_request_budget(self) -> None:
        if self._cycle_requests_made >= self._cycle_request_limit:
            raise BasketballRequestBudgetExhausted(
                "basketball request budget exhausted",
                category="REQUEST_BUDGET",
            )
        elapsed = time.monotonic() - self._last_request_at
        delay = self.settings.minimum_request_interval_seconds - elapsed
        if delay > 0:
            time.sleep(delay)
        self._cycle_requests_made += 1
        self._last_request_at = time.monotonic()

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
                self._consume_request_budget()
                response = self.session.get(
                    f"{self.settings.api_base_url}/{endpoint.lstrip('/')}",
                    params=params,
                    headers={"x-apisports-key": self.settings.api_key},
                    timeout=self.settings.request_timeout_seconds,
                )
                status = int(getattr(response, "status_code", 200))
                quota_limit, quota_remaining, retry_after = (
                    self._response_limits(response)
                )
                if status in {401, 403, 404, 429}:
                    if status in {401, 403}:
                        error_type = "AUTH_OR_ENTITLEMENT"
                    elif status == 404:
                        error_type = "ENDPOINT_UNAVAILABLE"
                    elif quota_remaining == 0:
                        error_type = "QUOTA"
                    else:
                        error_type = "RATE_LIMIT"
                    self._observe(
                        endpoint, success=False, status_code=status,
                        error_type=error_type, call_id=call_id,
                        quota_limit=quota_limit,
                        quota_remaining=quota_remaining,
                        retry_after_seconds=retry_after,
                    )
                    raise BasketballProviderUnavailable(
                        f"non-retryable HTTP {status}",
                        category=error_type,
                        status_code=status,
                        retry_after_seconds=retry_after,
                        quota_limit=quota_limit,
                        quota_remaining=quota_remaining,
                    )
                if 400 <= status < 500:
                    self._observe(
                        endpoint,
                        success=False,
                        status_code=status,
                        error_type="PROVIDER_4XX",
                        call_id=call_id,
                        quota_limit=quota_limit,
                        quota_remaining=quota_remaining,
                        retry_after_seconds=retry_after,
                    )
                    raise BasketballProviderUnavailable(
                        f"non-retryable HTTP {status}",
                        category="PROVIDER_4XX",
                        status_code=status,
                        retry_after_seconds=retry_after,
                        quota_limit=quota_limit,
                        quota_remaining=quota_remaining,
                    )
                if status >= 500:
                    raise BasketballProviderError(
                        f"retryable HTTP {status}",
                        category="UPSTREAM_5XX",
                        status_code=status,
                        quota_limit=quota_limit,
                        quota_remaining=quota_remaining,
                    )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise BasketballProviderError(
                        "provider returned a non-object response"
                    )
                provider_errors = payload.get("errors")
                if provider_errors:
                    category = self._provider_error_category(provider_errors)
                    self._observe(
                        endpoint,
                        success=False,
                        status_code=status,
                        error_type=category,
                        call_id=call_id,
                        quota_limit=quota_limit,
                        quota_remaining=quota_remaining,
                        retry_after_seconds=retry_after,
                    )
                    raise BasketballProviderUnavailable(
                        "provider returned an application error",
                        category=category,
                        status_code=status,
                        retry_after_seconds=retry_after,
                        quota_limit=quota_limit,
                        quota_remaining=quota_remaining,
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
                    quota_limit=quota_limit,
                    quota_remaining=quota_remaining,
                    retry_after_seconds=retry_after,
                )
                return rows
            except (
                BasketballProviderUnavailable,
                BasketballRequestBudgetExhausted,
            ):
                raise
            except Exception as exc:
                last_error = exc
                status = getattr(response, "status_code", None)
                quota_limit, quota_remaining, retry_after = (
                    self._response_limits(response)
                    if response is not None
                    else (None, None, None)
                )
                if attempt >= self.settings.retry_attempts:
                    self._observe(
                        endpoint, success=False, status_code=status,
                        error_type=(
                            getattr(exc, "category", "")
                            or type(exc).__name__
                        ),
                        call_id=call_id,
                        quota_limit=quota_limit,
                        quota_remaining=quota_remaining,
                        retry_after_seconds=retry_after,
                    )
                    break
                time.sleep(
                    self.settings.retry_backoff_seconds * (2 ** (attempt - 1))
                )
        raise BasketballProviderError(
            f"{endpoint} failed: {type(last_error).__name__}",
            category=(
                getattr(last_error, "category", "") or "NETWORK_OR_UPSTREAM"
            ),
            status_code=getattr(last_error, "status_code", None),
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
