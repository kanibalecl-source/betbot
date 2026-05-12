from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Tuple
import math

from .utils import clamp, num


@dataclass
class XGResultV5:
    home_xg: float
    away_xg: float
    home_xg_open_play: float
    away_xg_open_play: float
    home_xg_set_piece: float
    away_xg_set_piece: float
    data_quality: float
    explanation: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AdvancedXGEngineV5:
    """Shot/event xG first, aggregate/team xG fallback second.

    This engine never reads bookmaker odds.
    """

    def shot_xg(self, shot: Dict[str, Any]) -> float:
        distance = num(shot.get("distance"), 18.0)
        angle = num(shot.get("angle"), 0.45)  # radians-ish proxy 0..1
        body = str(shot.get("body_part", "foot")).lower()
        situation = str(shot.get("situation", "open_play")).lower()
        big = 1.0 if shot.get("big_chance") else 0.0
        one_on_one = 1.0 if shot.get("one_on_one") else 0.0
        pressure = num(shot.get("pressure"), 0.35)
        cutback = 1.0 if shot.get("assist_type") == "cutback" else 0.0

        z = (
            -2.65
            - 0.085 * distance
            + 1.55 * angle
            + 1.10 * big
            + 1.35 * one_on_one
            + 0.85 * cutback
            - 0.55 * pressure
        )
        if body == "head":
            z -= 0.35
        elif body in {"weak_foot", "other"}:
            z -= 0.20
        if situation in {"penalty"}:
            return 0.76
        if situation in {"direct_free_kick"}:
            z -= 0.65
        if situation in {"corner", "set_piece"}:
            z -= 0.10
        return round(clamp(1 / (1 + math.exp(-z)), 0.005, 0.80), 4)

    def from_events(self, events: Iterable[Dict[str, Any]], home_team: str, away_team: str) -> Tuple[float, float, float, float]:
        hxg = axg = hsp = asp = 0.0
        for ev in events or []:
            if str(ev.get("type", "")).lower() not in {"shot", "goal_attempt"}:
                continue
            xg = num(ev.get("xg"), None)
            if xg is None:
                xg = self.shot_xg(ev)
            team = ev.get("team")
            situation = str(ev.get("situation", "open_play")).lower()
            is_set = situation in {"corner", "set_piece", "free_kick", "direct_free_kick", "penalty"}
            if team == home_team or ev.get("side") == "home":
                hxg += xg
                if is_set: hsp += xg
            elif team == away_team or ev.get("side") == "away":
                axg += xg
                if is_set: asp += xg
        return hxg, axg, hsp, asp

    def from_aggregates(self, match: Dict[str, Any]) -> Tuple[float, float]:
        hxg = num(match.get("home_xg"), 0.0)
        axg = num(match.get("away_xg"), 0.0)
        if hxg > 0 or axg > 0:
            return hxg, axg
        h_shots = num(match.get("home_shots"), 11.2)
        a_shots = num(match.get("away_shots"), 9.8)
        h_sot = num(match.get("home_sot"), 4.0)
        a_sot = num(match.get("away_sot"), 3.4)
        h_big = num(match.get("home_big_chances"), 1.3)
        a_big = num(match.get("away_big_chances"), 1.0)
        h_danger = num(match.get("home_dangerous_attacks"), 38)
        a_danger = num(match.get("away_dangerous_attacks"), 33)
        hxg = 0.055*h_shots + 0.085*h_sot + 0.28*h_big + 0.004*h_danger
        axg = 0.055*a_shots + 0.085*a_sot + 0.28*a_big + 0.004*a_danger
        return hxg, axg

    def calculate(self, match: Dict[str, Any], data_quality: float = 0.5) -> XGResultV5:
        home = str(match.get("home_team", "HOME"))
        away = str(match.get("away_team", "AWAY"))
        explanation: List[str] = []
        events = match.get("events") or []
        if events:
            hxg, axg, hsp, asp = self.from_events(events, home, away)
            if hxg + axg > 0:
                explanation.append("shot/event based xG used")
            else:
                hxg, axg = self.from_aggregates(match)
                hsp = hxg * 0.22; asp = axg * 0.22
                explanation.append("events present but no shots recognized; aggregate fallback used")
        else:
            hxg, axg = self.from_aggregates(match)
            hsp = hxg * num(match.get("home_set_piece_share"), 0.22)
            asp = axg * num(match.get("away_set_piece_share"), 0.22)
            explanation.append("aggregate/proxy xG used")

        home_adv = num(match.get("home_advantage"), 0.08)
        tactical_open = clamp(num(match.get("tactical_openness"), 1.0), 0.72, 1.35)
        weather_drag = clamp(num(match.get("weather_drag"), 0.0), 0.0, 0.25)
        h_fatigue = clamp(num(match.get("home_fatigue"), 0.0), 0.0, 0.30)
        a_fatigue = clamp(num(match.get("away_fatigue"), 0.0), 0.0, 0.30)
        h_lineup = clamp(num(match.get("home_lineup_strength"), 1.0), 0.55, 1.25)
        a_lineup = clamp(num(match.get("away_lineup_strength"), 1.0), 0.55, 1.25)
        h_def_weak = clamp(num(match.get("away_defense_weakness"), 1.0), 0.65, 1.45)
        a_def_weak = clamp(num(match.get("home_defense_weakness"), 1.0), 0.65, 1.45)

        hxg = hxg * (1 + home_adv) * tactical_open * (1 - weather_drag) * (1 - h_fatigue) * h_lineup * h_def_weak
        axg = axg * tactical_open * (1 - weather_drag) * (1 - a_fatigue) * a_lineup * a_def_weak

        hxg = clamp(hxg, 0.05, 4.80)
        axg = clamp(axg, 0.05, 4.20)
        return XGResultV5(
            round(hxg, 4), round(axg, 4),
            round(max(0.0, hxg - hsp), 4), round(max(0.0, axg - asp), 4),
            round(hsp, 4), round(asp, 4), round(data_quality, 4), explanation,
        )
