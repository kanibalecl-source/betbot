from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

import requests

from .config import SportradarSettings


class SportradarProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderResponse:
    payload: dict[str, Any]
    url: str
    status_code: int
    etag: str
    cache_control: str
    request_id: str


SPORT_PATHS = {
    "football": "soccer",
    "volleyball": "volleyball",
    "handball": "handball",
}

SPORT_IDS = {
    "football": "sr:sport:1",
    "volleyball": "sr:sport:23",
    "handball": "sr:sport:6",
}


class SportradarClient:
    def __init__(
        self,
        settings: SportradarSettings,
        *,
        session: requests.Session | None = None,
        observer: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.settings = settings
        self.session = session or requests.Session()
        self.observer = observer
        self._last_request_monotonic = 0.0

    def _notify(self, event: dict[str, Any]) -> None:
        if self.observer is not None:
            self.observer(event)

    def _pace(self) -> None:
        elapsed = time.monotonic() - self._last_request_monotonic
        remaining = self.settings.request_interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _get(self, url: str) -> ProviderResponse:
        last_error = ""
        for attempt in range(self.settings.maximum_retries + 1):
            self._pace()
            started = time.monotonic()
            status_code = 0
            try:
                response = self.session.get(
                    url,
                    headers={
                        "accept": "application/json",
                        "x-api-key": self.settings.api_key,
                    },
                    timeout=self.settings.request_timeout_seconds,
                )
                self._last_request_monotonic = time.monotonic()
                status_code = int(response.status_code)
                duration_ms = int((time.monotonic() - started) * 1000)
                self._notify(
                    {
                        "url": url,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                        "attempt": attempt + 1,
                        "success": status_code == 200,
                    }
                )
                if status_code == 200:
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise SportradarProviderError(
                            f"non-object JSON response from {url}"
                        )
                    return ProviderResponse(
                        payload=payload,
                        url=url,
                        status_code=status_code,
                        etag=str(response.headers.get("etag", "")),
                        cache_control=str(response.headers.get("cache-control", "")),
                        request_id=str(
                            response.headers.get("x-amzn-requestid", "")
                            or response.headers.get("x-request-id", "")
                        ),
                    )
                last_error = f"HTTP {status_code}"
                if status_code not in {429, 500, 502, 503, 504}:
                    break
            except (requests.RequestException, ValueError, SportradarProviderError) as exc:
                self._last_request_monotonic = time.monotonic()
                last_error = f"{type(exc).__name__}: {exc}"
                self._notify(
                    {
                        "url": url,
                        "status_code": status_code,
                        "duration_ms": int((time.monotonic() - started) * 1000),
                        "attempt": attempt + 1,
                        "success": False,
                        "error_type": type(exc).__name__,
                    }
                )
            if attempt < self.settings.maximum_retries:
                time.sleep(min(4.0, 1.0 + attempt))
        raise SportradarProviderError(f"{url} failed: {last_error[:240]}")

    def daily_summaries(self, sport: str, day: date) -> ProviderResponse:
        try:
            path = SPORT_PATHS[sport]
        except KeyError as exc:
            raise ValueError(f"unsupported sport: {sport}") from exc
        url = (
            f"https://api.sportradar.com/{path}/{self.settings.access_level}/v2/"
            f"{self.settings.language}/schedules/{day.isoformat()}/summaries.json"
        )
        if sport == "football":
            url = (
                f"https://api.sportradar.com/soccer/{self.settings.access_level}/v4/"
                f"{self.settings.language}/schedules/{day.isoformat()}/summaries.json"
            )
        return self._get(url)

    def odds_sports(self) -> ProviderResponse:
        return self._get(
            "https://api.sportradar.com/oddscomparison-rowt1/"
            f"{self.settings.language}/eu/sports.json"
        )

    def odds_daily_schedule(self, sport: str, day: date) -> ProviderResponse:
        try:
            sport_id = SPORT_IDS[sport]
        except KeyError as exc:
            raise ValueError(f"unsupported sport: {sport}") from exc
        return self._get(
            "https://api.sportradar.com/oddscomparison-rowt1/"
            f"{self.settings.language}/eu/sports/{sport_id}/"
            f"{day.isoformat()}/schedule.json"
        )

    def odds_event_markets(self, event_id: str) -> ProviderResponse:
        safe_id = str(event_id).strip()
        if not safe_id.startswith(("sr:match:", "sr:sport_event:")):
            raise ValueError("invalid Sportradar event id")
        return self._get(
            "https://api.sportradar.com/oddscomparison-rowt1/"
            f"{self.settings.language}/eu/sport_events/{safe_id}/markets.json"
        )

