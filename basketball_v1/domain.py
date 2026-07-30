from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


FINISHED_STATUSES = {
    "FT", "AOT", "AP", "AW", "ENDED", "CLOSED", "FINISHED",
}
VOID_STATUSES = {
    "CANC", "ABD", "INTR", "POST", "CANCELLED", "ABANDONED",
    "POSTPONED", "SUSPENDED",
}
UPCOMING_STATUSES = {"NS", "TBD", "NOT_STARTED", "SCHEDULED"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _integer(value: Any) -> int | None:
    if isinstance(value, dict):
        value = value.get("total")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class BasketballGame:
    game_id: str
    scheduled_at: str
    status: str
    league_id: str
    league_name: str
    country: str
    season: str
    home_team_id: str
    home_team: str
    away_team_id: str
    away_team: str
    home_score: int | None
    away_score: int | None
    overtime: bool
    raw: dict[str, Any]

    @property
    def finished(self) -> bool:
        return self.status.upper() in FINISHED_STATUSES

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "BasketballGame":
        league = payload.get("league")
        league = league if isinstance(league, dict) else {}
        country = payload.get("country")
        country = country if isinstance(country, dict) else {}
        teams = payload.get("teams")
        teams = teams if isinstance(teams, dict) else {}
        home = teams.get("home")
        home = home if isinstance(home, dict) else {}
        away = teams.get("away")
        away = away if isinstance(away, dict) else {}
        scores = payload.get("scores")
        scores = scores if isinstance(scores, dict) else {}
        status_raw = payload.get("status")
        status = (
            status_raw.get("short") or status_raw.get("long") or "UNKNOWN"
            if isinstance(status_raw, dict)
            else status_raw or "UNKNOWN"
        )
        home_score = _integer(scores.get("home"))
        away_score = _integer(scores.get("away"))
        overtime = False
        for side in ("home", "away"):
            value = scores.get(side)
            if isinstance(value, dict):
                overtime = overtime or _integer(value.get("over_time")) not in {
                    None, 0,
                }
        return cls(
            game_id=str(payload.get("id") or ""),
            scheduled_at=str(
                payload.get("date") or payload.get("timestamp") or ""
            ),
            status=str(status),
            league_id=str(league.get("id") or ""),
            league_name=str(league.get("name") or "UNKNOWN"),
            country=str(
                country.get("name") or country.get("code")
                or league.get("country") or ""
            ),
            season=str(league.get("season") or payload.get("season") or ""),
            home_team_id=str(home.get("id") or ""),
            home_team=str(home.get("name") or ""),
            away_team_id=str(away.get("id") or ""),
            away_team=str(away.get("name") or ""),
            home_score=home_score,
            away_score=away_score,
            overtime=overtime,
            raw=payload,
        )


@dataclass(frozen=True)
class BasketballOddsQuote:
    game_id: str
    bookmaker_id: str
    bookmaker: str
    market: str
    outcome: str
    line: float | None
    odds: float
    observed_at: str

