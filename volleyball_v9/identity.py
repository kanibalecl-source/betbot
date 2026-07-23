from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime

from .domain import VolleyballGame


PROVIDER = "api-sports-volleyball"
_SPACE = re.compile(r"\s+")


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    return _SPACE.sub(" ", text)


def stable_key(kind: str, source_id: str, display_name: str) -> str:
    normalized = normalize_name(display_name)
    identity = str(source_id or "").strip() or f"name:{normalized}"
    material = f"volleyball|{PROVIDER}|{kind}|{identity}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def game_fingerprint(game: VolleyballGame) -> str:
    material = "|".join(
        [
            str(game.scheduled_at).strip(),
            str(game.league_id).strip(),
            normalize_name(game.home_team),
            normalize_name(game.away_team),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IdentityRecord:
    game_id: str
    team_home_key: str
    team_away_key: str
    league_key: str
    fingerprint: str


def validate_game(game: VolleyballGame) -> tuple[str, ...]:
    reasons: list[str] = []
    required = {
        "game_id": game.game_id,
        "scheduled_at": game.scheduled_at,
        "league_id": game.league_id,
        "home_team_id": game.home_team_id,
        "home_team": game.home_team,
        "away_team_id": game.away_team_id,
        "away_team": game.away_team,
    }
    reasons.extend(f"missing_{name}" for name, value in required.items() if not str(value).strip())
    if game.home_team_id and game.home_team_id == game.away_team_id:
        reasons.append("same_team_id")
    if normalize_name(game.home_team) and normalize_name(game.home_team) == normalize_name(game.away_team):
        reasons.append("same_team_name")
    try:
        parsed = datetime.fromisoformat(str(game.scheduled_at).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            reasons.append("scheduled_at_without_timezone")
    except ValueError:
        reasons.append("invalid_scheduled_at")
    for label, value in (("home_sets", game.home_sets), ("away_sets", game.away_sets)):
        if value is not None and (value < 0 or value > 10):
            reasons.append(f"invalid_{label}")
    if game.finished and game.home_sets is not None and game.away_sets is not None:
        if game.home_sets == game.away_sets:
            reasons.append("finished_match_tied_sets")
    return tuple(sorted(set(reasons)))


def identity_for(game: VolleyballGame) -> IdentityRecord:
    return IdentityRecord(
        game_id=game.game_id,
        team_home_key=stable_key("team", game.home_team_id, game.home_team),
        team_away_key=stable_key("team", game.away_team_id, game.away_team),
        league_key=stable_key("league", game.league_id, game.league_name),
        fingerprint=game_fingerprint(game),
    )
