from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional
import math

from .feature_factory import MatchFeaturesV4


def _shot_xg(shot: Dict[str, Any]) -> float:
    """Simple explainable shot xG estimator when provider gives shot events.

    Expected fields: distance_m, angle_deg, body_part, situation, big_chance.
    """
    distance = max(float(shot.get("distance_m", 18.0) or 18.0), 1.0)
    angle = max(min(float(shot.get("angle_deg", 25.0) or 25.0), 80.0), 1.0)
    logit = -2.15 - 0.095*distance + 0.030*angle
    if shot.get("big_chance"):
        logit += 1.15
    if str(shot.get("situation", "")).lower() in {"counter", "fast_break"}:
        logit += 0.25
    if str(shot.get("situation", "")).lower() in {"corner", "free_kick"}:
        logit -= 0.12
    if str(shot.get("body_part", "")).lower() == "header":
        logit -= 0.22
    p = 1.0 / (1.0 + math.exp(-logit))
    return max(0.005, min(0.78, p))


@dataclass
class XGResultV4:
    home_xg: float
    away_xg: float
    method: str
    explain: Dict[str, Any]


class XGEngineV4:
    """Multi-layer xG engine. Uses direct shot xG if available, otherwise proxies."""

    def from_shots(self, events: Iterable[Dict[str, Any]], home_team: str, away_team: str) -> Optional[XGResultV4]:
        events = list(events or [])
        shot_events = [e for e in events if str(e.get("type", "")).lower() in {"shot", "goal", "miss", "saved_shot"}]
        if len(shot_events) < 4:
            return None
        hxg = axg = 0.0
        home_shots = away_shots = 0
        for s in shot_events:
            val = float(s.get("xg", 0) or 0) or _shot_xg(s)
            team = str(s.get("team", ""))
            if team == home_team or s.get("is_home") is True:
                hxg += val; home_shots += 1
            elif team == away_team or s.get("is_home") is False:
                axg += val; away_shots += 1
        return XGResultV4(round(hxg, 4), round(axg, 4), "shot_event_xg", {"home_shots": home_shots, "away_shots": away_shots})

    def pre_match_xg(self, f: MatchFeaturesV4) -> XGResultV4:
        home_advantage = 0.18
        league_baseline_home = 1.38
        league_baseline_away = 1.13

        home = (
            0.30*league_baseline_home +
            0.38*f.home_attack_power +
            0.27*f.away_defense_weakness +
            0.12*f.home_set_piece_threat +
            home_advantage
        )
        away = (
            0.31*league_baseline_away +
            0.39*f.away_attack_power +
            0.27*f.home_defense_weakness +
            0.11*f.away_set_piece_threat
        )

        tempo_boost = max(0.78, min(1.24, (f.home_tempo + f.away_tempo) / 2.0))
        tactical = f.tactical_openness
        drag = 1.0 - f.weather_drag

        home *= tempo_boost * tactical * drag * f.home_lineup_strength * (1.0 - f.home_fatigue)
        away *= tempo_boost * tactical * drag * f.away_lineup_strength * (1.0 - f.away_fatigue)

        home = max(0.18, min(3.80, home))
        away = max(0.12, min(3.50, away))
        return XGResultV4(round(home, 4), round(away, 4), "rocket_feature_xg", {
            "tempo_boost": round(tempo_boost, 4),
            "tactical_openness": f.tactical_openness,
            "weather_drag": f.weather_drag,
            "lineup_home": f.home_lineup_strength,
            "lineup_away": f.away_lineup_strength,
        })
