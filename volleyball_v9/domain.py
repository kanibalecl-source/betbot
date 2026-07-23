from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


FINISHED_STATUSES = {"FT", "AW", "ENDED", "CLOSED", "AFTER_GOLDEN_SET"}
VOID_STATUSES = {"CANC", "ABD", "INTR", "POST", "CANCELLED", "ABANDONED", "POSTPONED"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _integer(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class VolleyballGame:
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
    home_sets: int | None
    away_sets: int | None
    raw: dict[str, Any]

    @property
    def finished(self) -> bool:
        return self.status.upper() in FINISHED_STATUSES

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "VolleyballGame":
        league = payload.get("league") if isinstance(payload.get("league"), dict) else {}
        country = payload.get("country") if isinstance(payload.get("country"), dict) else {}
        teams = payload.get("teams") if isinstance(payload.get("teams"), dict) else {}
        home = teams.get("home") if isinstance(teams.get("home"), dict) else {}
        away = teams.get("away") if isinstance(teams.get("away"), dict) else {}
        scores = payload.get("scores") if isinstance(payload.get("scores"), dict) else {}
        home_score = scores.get("home")
        away_score = scores.get("away")
        if isinstance(home_score, dict):
            home_score = home_score.get("total") or home_score.get("sets")
        if isinstance(away_score, dict):
            away_score = away_score.get("total") or away_score.get("sets")
        return cls(
            game_id=str(payload.get("id") or ""),
            scheduled_at=str(payload.get("date") or payload.get("timestamp") or ""),
            status=str(payload.get("status", {}).get("short") if isinstance(payload.get("status"), dict) else payload.get("status") or "UNKNOWN"),
            league_id=str(league.get("id") or ""),
            league_name=str(league.get("name") or "UNKNOWN"),
            country=str(country.get("name") or country.get("code") or ""),
            season=str(league.get("season") or payload.get("season") or ""),
            home_team_id=str(home.get("id") or ""),
            home_team=str(home.get("name") or ""),
            away_team_id=str(away.get("id") or ""),
            away_team=str(away.get("name") or ""),
            home_sets=_integer(home_score),
            away_sets=_integer(away_score),
            raw=payload,
        )


@dataclass(frozen=True)
class OddsQuote:
    game_id: str
    bookmaker_id: str
    bookmaker: str
    market: str
    outcome: str
    odds: float
    observed_at: str


@dataclass(frozen=True)
class ModelPrediction:
    home_probability: float
    away_probability: float
    home_fair_odds: float
    away_fair_odds: float
    home_rating: float
    away_rating: float
    home_matches: int
    away_matches: int
    confidence: float

