"""Shared, fail-closed API-Sports transport used by shadow collectors.

The transport owns only provider communication.  It never writes training
data, creates model candidates or changes an active model.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable, Type


class ResilientProviderError(RuntimeError):
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


class ResilientRequestBudgetExhausted(ResilientProviderError):
    pass


Observer = Callable[[dict[str, Any]], None]


class ApiSportsResilientTransport:
    """Bounded API transport with quota awareness and deterministic retries."""

    def __init__(
        self,
        *,
        sport: str,
        settings: Any,
        session: Any,
        observer: Observer | None,
        provider_error_type: Type[ResilientProviderError],
        request_budget_error_type: Type[ResilientRequestBudgetExhausted],
    ) -> None:
        self.sport = str(sport)
        self.settings = settings
        self.session = session
        self.observer = observer
        self.provider_error_type = provider_error_type
        self.request_budget_error_type = request_budget_error_type
        self._cycle_request_limit = int(settings.maximum_requests_per_cycle)
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
    def response_limits(
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
    def provider_error_category(raw: Any) -> str:
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
            raise self.request_budget_error_type(
                f"{self.sport} request budget exhausted",
                category="REQUEST_BUDGET",
            )
        elapsed = time.monotonic() - self._last_request_at
        delay = float(self.settings.minimum_request_interval_seconds) - elapsed
        if delay > 0:
            time.sleep(delay)
        self._cycle_requests_made += 1
        self._last_request_at = time.monotonic()

    def _observe(self, **payload: Any) -> None:
        if self.observer is not None:
            self.observer(payload)

    def get(
        self, endpoint: str, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        params_json = json.dumps(params, sort_keys=True, separators=(",", ":"))
        call_id = hashlib.sha256(
            f"{endpoint}|{params_json}|{time.time_ns()}".encode("utf-8")
        ).hexdigest()
        started = time.monotonic()
        last_error: Exception | None = None

        for attempt in range(1, int(self.settings.retry_attempts) + 1):
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
                    self.response_limits(response)
                )

                if status in {401, 403, 404, 429}:
                    if status == 401:
                        category = "AUTH"
                    elif status == 403:
                        category = "ENTITLEMENT"
                    elif status == 404:
                        category = "ENDPOINT_UNAVAILABLE"
                    elif quota_remaining == 0:
                        category = "QUOTA"
                    else:
                        category = "RATE_LIMIT"
                    self._observe(
                        call_id=f"{call_id}:{attempt}", endpoint=endpoint,
                        params_json=params_json, attempt=attempt,
                        status="FAILED", http_status=status, rows=0,
                        duration_ms=int((time.monotonic() - started) * 1000),
                        remaining=quota_remaining, error_type=category,
                        error=f"HTTP {status}", quota_limit=quota_limit,
                        retry_after_seconds=retry_after,
                    )
                    raise self.provider_error_type(
                        f"non-retryable HTTP {status}", category=category,
                        status_code=status, retry_after_seconds=retry_after,
                        quota_limit=quota_limit,
                        quota_remaining=quota_remaining,
                    )
                if 400 <= status < 500:
                    category = "PROVIDER_4XX"
                    self._observe(
                        call_id=f"{call_id}:{attempt}", endpoint=endpoint,
                        params_json=params_json, attempt=attempt,
                        status="FAILED", http_status=status, rows=0,
                        duration_ms=int((time.monotonic() - started) * 1000),
                        remaining=quota_remaining, error_type=category,
                        error=f"HTTP {status}", quota_limit=quota_limit,
                        retry_after_seconds=retry_after,
                    )
                    raise self.provider_error_type(
                        f"non-retryable HTTP {status}", category=category,
                        status_code=status, retry_after_seconds=retry_after,
                        quota_limit=quota_limit,
                        quota_remaining=quota_remaining,
                    )
                if status >= 500:
                    raise self.provider_error_type(
                        f"retryable HTTP {status}", category="UPSTREAM_5XX",
                        status_code=status, quota_limit=quota_limit,
                        quota_remaining=quota_remaining,
                    )

                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise self.provider_error_type(
                        "API-Sports returned a non-object response",
                        category="PROVIDER_RESPONSE",
                    )
                errors = payload.get("errors")
                if errors:
                    category = self.provider_error_category(errors)
                    self._observe(
                        call_id=f"{call_id}:{attempt}", endpoint=endpoint,
                        params_json=params_json, attempt=attempt,
                        status="FAILED", http_status=status, rows=0,
                        duration_ms=int((time.monotonic() - started) * 1000),
                        remaining=quota_remaining, error_type=category,
                        error="API-Sports application error",
                        quota_limit=quota_limit,
                        retry_after_seconds=retry_after,
                    )
                    raise self.provider_error_type(
                        "API-Sports application error", category=category,
                        status_code=status, retry_after_seconds=retry_after,
                        quota_limit=quota_limit,
                        quota_remaining=quota_remaining,
                    )
                rows = payload.get("response", [])
                if not isinstance(rows, list):
                    raise self.provider_error_type(
                        "API-Sports response field is not a list",
                        category="PROVIDER_RESPONSE",
                    )
                clean_rows = [row for row in rows if isinstance(row, dict)]
                self._observe(
                    call_id=f"{call_id}:{attempt}", endpoint=endpoint,
                    params_json=params_json, attempt=attempt,
                    status="SUCCESS", http_status=status,
                    rows=len(clean_rows),
                    duration_ms=int((time.monotonic() - started) * 1000),
                    remaining=quota_remaining, quota_limit=quota_limit,
                    retry_after_seconds=retry_after,
                )
                return clean_rows
            except self.request_budget_error_type:
                raise
            except self.provider_error_type as exc:
                if getattr(exc, "category", "") in {
                    "AUTH", "ENTITLEMENT", "QUOTA", "RATE_LIMIT",
                    "ENDPOINT_UNAVAILABLE", "PROVIDER_4XX",
                    "PROVIDER_RESPONSE", "COVERAGE",
                }:
                    raise
                last_error = exc
            except Exception as exc:
                last_error = exc

            status = int(getattr(response, "status_code", 0) or 0)
            quota_limit, quota_remaining, retry_after = (
                self.response_limits(response)
                if response is not None else (None, None, None)
            )
            final_attempt = attempt >= int(self.settings.retry_attempts)
            self._observe(
                call_id=f"{call_id}:{attempt}", endpoint=endpoint,
                params_json=params_json, attempt=attempt,
                status="FAILED" if final_attempt else "RETRY",
                http_status=status, rows=0,
                duration_ms=int((time.monotonic() - started) * 1000),
                remaining=quota_remaining,
                error_type=(
                    getattr(last_error, "category", "")
                    or type(last_error).__name__
                ),
                error=str(last_error)[:500], quota_limit=quota_limit,
                retry_after_seconds=retry_after,
            )
            if final_attempt:
                break
            time.sleep(
                float(self.settings.retry_backoff_seconds)
                * (2 ** (attempt - 1))
            )

        raise self.provider_error_type(
            f"{endpoint} failed: {type(last_error).__name__}",
            category=(
                getattr(last_error, "category", "")
                or "NETWORK_OR_UPSTREAM"
            ),
            status_code=getattr(last_error, "status_code", None),
        )
