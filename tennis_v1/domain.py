from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


FINISHED_STATUSES = {"closed", "ended", "finished", "complete", "completed"}
VOID_STATUSES = {
    "cancelled", "canceled", "abandoned", "postponed", "interrupted",
    "walkover", "walk_over", "retired",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    parts = [part for part in text.split() if part]
    return " ".join(sorted(parts))


def _integer(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class TennisMatch:
    event_id: str
    scheduled_at: str
    status: str
    tour: str
    competition_id: str
    competition_name: str
    competition_level: str
    competition_type: str
    surface: str
    best_of: int
    player1_id: str
    player1_name: str
    player2_id: str
    player2_name: str
    player1_sets: int | None
    player2_sets: int | None
    winner_id: str
    retired: bool
    raw: dict[str, Any]

    @property
    def finished(self) -> bool:
        return self.status.lower() in FINISHED_STATUSES and bool(self.winner_id)

    @property
    def void(self) -> bool:
        return self.retired or self.status.lower() in VOID_STATUSES

    @property
    def singles(self) -> bool:
        return self.competition_type.lower() in {"singles", "single", ""}

    @classmethod
    def from_sportradar(cls, payload: dict[str, Any]) -> "TennisMatch":
        event = payload.get("sport_event")
        if not isinstance(event, dict):
            event = payload
        context = event.get("sport_event_context")
        context = context if isinstance(context, dict) else {}
        category = context.get("category")
        category = category if isinstance(category, dict) else {}
        competition = context.get("competition")
        competition = competition if isinstance(competition, dict) else {}
        mode = context.get("mode")
        mode = mode if isinstance(mode, dict) else {}
        props = event.get("sport_event_properties")
        props = props if isinstance(props, dict) else {}
        competitors = event.get("competitors")
        competitors = competitors if isinstance(competitors, list) else []
        home = next(
            (item for item in competitors if item.get("qualifier") == "home"),
            competitors[0] if competitors else {},
        )
        away = next(
            (item for item in competitors if item.get("qualifier") == "away"),
            competitors[1] if len(competitors) > 1 else {},
        )
        status_data = payload.get("sport_event_status")
        status_data = status_data if isinstance(status_data, dict) else {}
        period_scores = status_data.get("period_scores")
        period_scores = period_scores if isinstance(period_scores, list) else []
        home_sets = status_data.get("home_score")
        away_sets = status_data.get("away_score")
        if home_sets is None and period_scores:
            home_sets = sum(
                1 for item in period_scores
                if _integer(item.get("home_score")) is not None
                and _integer(item.get("away_score")) is not None
                and int(item["home_score"]) > int(item["away_score"])
            )
        if away_sets is None and period_scores:
            away_sets = sum(
                1 for item in period_scores
                if _integer(item.get("home_score")) is not None
                and _integer(item.get("away_score")) is not None
                and int(item["away_score"]) > int(item["home_score"])
            )
        winner_id = str(status_data.get("winner_id") or "")
        status = str(status_data.get("status") or "not_started").lower()
        match_status = str(status_data.get("match_status") or "").lower()
        retired = "retir" in match_status or "walkover" in match_status
        surface = str(
            props.get("surface")
            or competition.get("surface")
            or context.get("surface")
            or "unknown"
        ).lower()
        return cls(
            event_id=str(event.get("id") or ""),
            scheduled_at=str(event.get("start_time") or ""),
            status=status,
            tour=str(category.get("name") or ""),
            competition_id=str(competition.get("id") or ""),
            competition_name=str(competition.get("name") or ""),
            competition_level=str(competition.get("level") or ""),
            competition_type=str(competition.get("type") or ""),
            surface=surface,
            best_of=int(_integer(mode.get("best_of")) or 3),
            player1_id=str(home.get("id") or ""),
            player1_name=str(home.get("name") or ""),
            player2_id=str(away.get("id") or ""),
            player2_name=str(away.get("name") or ""),
            player1_sets=_integer(home_sets),
            player2_sets=_integer(away_sets),
            winner_id=winner_id,
            retired=retired,
            raw=payload,
        )


@dataclass(frozen=True)
class TennisOddsQuote:
    event_id: str
    bookmaker: str
    player_name: str
    odds: float
    observed_at: str
    source_event_id: str

