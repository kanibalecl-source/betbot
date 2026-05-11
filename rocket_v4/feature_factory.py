from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _per90(value: Any, matches: Any, default: float = 0.0) -> float:
    m = max(_num(matches, 0.0), 1.0)
    return _num(value, default) / m


@dataclass
class MatchFeaturesV4:
    home_team: str
    away_team: str
    league: str
    home_attack_power: float
    away_attack_power: float
    home_defense_weakness: float
    away_defense_weakness: float
    home_tempo: float
    away_tempo: float
    home_set_piece_threat: float
    away_set_piece_threat: float
    home_fatigue: float
    away_fatigue: float
    home_lineup_strength: float
    away_lineup_strength: float
    tactical_openness: float
    weather_drag: float
    data_quality: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FeatureFactoryV4:
    """Creates model features from raw match data without bookmaker odds."""

    def build(self, match: Dict[str, Any], data_quality: float = 0.5) -> MatchFeaturesV4:
        h_matches = _num(match.get("home_recent_matches"), 10)
        a_matches = _num(match.get("away_recent_matches"), 10)

        h_xg = _num(match.get("home_xg"), _per90(match.get("home_goals_for"), h_matches, 1.25))
        a_xg = _num(match.get("away_xg"), _per90(match.get("away_goals_for"), a_matches, 1.05))
        h_xga = _num(match.get("home_xga"), _per90(match.get("home_goals_against"), h_matches, 1.10))
        a_xga = _num(match.get("away_xga"), _per90(match.get("away_goals_against"), a_matches, 1.25))

        h_shots = _num(match.get("home_shots"), 11.5)
        a_shots = _num(match.get("away_shots"), 10.0)
        h_sot = _num(match.get("home_sot"), 4.1)
        a_sot = _num(match.get("away_sot"), 3.6)
        h_big = _num(match.get("home_big_chances"), 1.5)
        a_big = _num(match.get("away_big_chances"), 1.2)

        h_danger = _num(match.get("home_dangerous_attacks"), 40)
        a_danger = _num(match.get("away_dangerous_attacks"), 35)
        h_ppda = _num(match.get("home_ppda"), 10.5)
        a_ppda = _num(match.get("away_ppda"), 11.5)

        home_attack = 0.45*h_xg + 0.018*h_shots + 0.035*h_sot + 0.12*h_big + 0.004*h_danger
        away_attack = 0.45*a_xg + 0.018*a_shots + 0.035*a_sot + 0.12*a_big + 0.004*a_danger
        home_def_weak = 0.70*h_xga + 0.010*_num(match.get("home_shots_allowed"), 10.0) + 0.08*_num(match.get("home_big_chances_allowed"), 1.2)
        away_def_weak = 0.70*a_xga + 0.010*_num(match.get("away_shots_allowed"), 11.0) + 0.08*_num(match.get("away_big_chances_allowed"), 1.4)

        h_tempo = 0.45*(h_danger/45.0) + 0.35*(h_shots/12.0) + 0.20*(11.5/max(h_ppda, 5.0))
        a_tempo = 0.45*(a_danger/45.0) + 0.35*(a_shots/12.0) + 0.20*(11.5/max(a_ppda, 5.0))

        weather_drag = max(0.0, min(0.22, _num(match.get("weather_drag"), 0.0)))
        tactical_open = max(0.70, min(1.35, _num(match.get("tactical_openness"), (h_tempo+a_tempo)/2)))

        return MatchFeaturesV4(
            home_team=str(match.get("home_team", match.get("home", "HOME"))),
            away_team=str(match.get("away_team", match.get("away", "AWAY"))),
            league=str(match.get("league", "UNKNOWN")),
            home_attack_power=round(home_attack, 5),
            away_attack_power=round(away_attack, 5),
            home_defense_weakness=round(home_def_weak, 5),
            away_defense_weakness=round(away_def_weak, 5),
            home_tempo=round(h_tempo, 5),
            away_tempo=round(a_tempo, 5),
            home_set_piece_threat=_num(match.get("home_set_piece_xg"), 0.18),
            away_set_piece_threat=_num(match.get("away_set_piece_xg"), 0.15),
            home_fatigue=max(0.0, min(0.25, _num(match.get("home_fatigue"), 0.0))),
            away_fatigue=max(0.0, min(0.25, _num(match.get("away_fatigue"), 0.0))),
            home_lineup_strength=max(0.65, min(1.20, _num(match.get("home_lineup_strength"), 1.0))),
            away_lineup_strength=max(0.65, min(1.20, _num(match.get("away_lineup_strength"), 1.0))),
            tactical_openness=round(tactical_open, 5),
            weather_drag=weather_drag,
            data_quality=round(float(data_quality), 4),
        )
