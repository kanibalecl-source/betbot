from __future__ import annotations

import time
from typing import Any

import requests

from .config import TennisSettings


class TennisProviderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class TennisRateLimited(TennisProviderError):
    pass


class _JsonClient:
    def __init__(self, settings: TennisSettings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def _get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> tuple[Any, dict[str, str]]:
        last_error: Exception | None = None
        for attempt in range(self.settings.retry_attempts):
            try:
                response = self.session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=self.settings.request_timeout_seconds,
                )
                if response.status_code == 429:
                    raise TennisRateLimited(
                        f"Provider rate limit for {url}", status_code=429
                    )
                if response.status_code in {401, 403}:
                    raise TennisProviderError(
                        f"Provider authorization failed for {url}",
                        status_code=response.status_code,
                    )
                response.raise_for_status()
                return response.json(), {
                    key.lower(): value for key, value in response.headers.items()
                }
            except TennisRateLimited:
                raise
            except TennisProviderError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.settings.retry_attempts:
                    time.sleep(1.5 * (attempt + 1))
        raise TennisProviderError(str(last_error or "Provider request failed"))


class SportradarTennisClient(_JsonClient):
    def _url(self, suffix: str) -> str:
        return (
            f"{self.settings.sportradar_base_url}/"
            f"{self.settings.sportradar_access_level}/v3/en/{suffix.lstrip('/')}"
        )

    def daily_summaries(self, day: str) -> list[dict[str, Any]]:
        payload, _ = self._get(
            self._url(f"schedules/{day}/summaries.json"),
            headers={
                "accept": "application/json",
                "x-api-key": self.settings.sportradar_api_key,
            },
        )
        rows = payload.get("summaries", []) if isinstance(payload, dict) else []
        return rows if isinstance(rows, list) else []

    def rankings(self) -> list[dict[str, Any]]:
        payload, _ = self._get(
            self._url("rankings.json"),
            headers={
                "accept": "application/json",
                "x-api-key": self.settings.sportradar_api_key,
            },
        )
        rows = payload.get("rankings", []) if isinstance(payload, dict) else []
        return rows if isinstance(rows, list) else []


class TennisOddsClient(_JsonClient):
    def active_tennis_sports(self) -> list[dict[str, Any]]:
        payload, _ = self._get(
            f"{self.settings.odds_api_base_url}/sports",
            params={"apiKey": self.settings.odds_api_key},
        )
        rows = payload if isinstance(payload, list) else []
        return [
            row for row in rows
            if str(row.get("group", "")).lower() == "tennis"
            and bool(row.get("active", True))
        ]

    def odds(self, sport_key: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
        payload, headers = self._get(
            f"{self.settings.odds_api_base_url}/sports/{sport_key}/odds",
            params={
                "apiKey": self.settings.odds_api_key,
                "regions": self.settings.odds_regions,
                "markets": "h2h",
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            },
        )
        return (payload if isinstance(payload, list) else []), headers

