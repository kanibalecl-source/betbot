"""
Advanced Live Engine

Dodatkowa warstwa analizy LIVE. Moduł nie zmienia istniejącej logiki typowania,
nie uruchamia żadnej pętli po imporcie i bezpiecznie zwraca neutralne wartości,
gdy API nie dostarczy części statystyk.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            value = value.replace("%", "").replace(",", ".").strip()
        return float(value)
    except Exception:
        return default


def _stat(stats: Dict[str, Any], key: str, default: float = 0.0) -> float:
    return _to_float(stats.get(key), default)


class AdvancedLiveEngine:
    """Wylicza tempo, pressure, momentum i sygnały live bez zmiany starej logiki."""

    def enrich_match(
        self,
        match: Dict[str, Any],
        stats: Optional[Dict[str, Any]] = None,
        odds: Optional[float] = None,
        base_signal: str = "NO SIGNAL",
        base_confidence: float = 0,
    ) -> Dict[str, Any]:
        stats = stats or {}

        minute = _to_float(match.get("minute"), 0)
        home_goals = _to_float(match.get("home_goals"), 0)
        away_goals = _to_float(match.get("away_goals"), 0)
        total_goals = home_goals + away_goals

        shots_on_goal = _stat(stats, "home_Shots on Goal") + _stat(stats, "away_Shots on Goal")
        total_shots = _stat(stats, "home_Total Shots") + _stat(stats, "away_Total Shots")
        dangerous_attacks = _stat(stats, "home_Dangerous Attacks") + _stat(stats, "away_Dangerous Attacks")
        attacks = _stat(stats, "home_Attacks") + _stat(stats, "away_Attacks")
        corners = _stat(stats, "home_Corner Kicks") + _stat(stats, "away_Corner Kicks")
        possession_home = _stat(stats, "home_Ball Possession", 50)
        possession_away = _stat(stats, "away_Ball Possession", 50)
        possession_balance = abs(possession_home - possession_away)

        safe_minute = max(minute, 1)
        shots_per_min = total_shots / safe_minute
        shots_on_goal_per_min = shots_on_goal / safe_minute
        dangerous_attacks_per_min = dangerous_attacks / safe_minute
        attacks_per_min = attacks / safe_minute
        corners_per_min = corners / safe_minute

        pressure_index = (
            shots_on_goal * 8.0
            + total_shots * 2.2
            + dangerous_attacks * 0.65
            + corners * 4.0
            + possession_balance * 0.35
        )
        pressure_index = max(0.0, min(100.0, pressure_index))

        tempo_score = (
            shots_per_min * 22.0
            + shots_on_goal_per_min * 30.0
            + dangerous_attacks_per_min * 17.0
            + attacks_per_min * 3.0
            + corners_per_min * 18.0
            + pressure_index * 0.30
        )
        tempo_score = max(0.0, min(100.0, tempo_score))

        momentum_score = pressure_index * 0.55 + tempo_score * 0.45
        if 35 <= minute <= 45 or 70 <= minute <= 90:
            momentum_score += 5
        if total_goals == 0 and minute >= 55:
            momentum_score += 4
        momentum_score = max(0.0, min(100.0, momentum_score))

        xg_pace = round((shots_on_goal * 0.18 + total_shots * 0.055 + dangerous_attacks * 0.012), 2)

        if tempo_score >= 72 and pressure_index >= 68:
            live_intensity = "VERY HIGH"
        elif tempo_score >= 55 or pressure_index >= 55:
            live_intensity = "HIGH"
        elif tempo_score >= 35 or pressure_index >= 35:
            live_intensity = "MEDIUM"
        else:
            live_intensity = "LOW"

        advanced_signal = "NO ADVANCED SIGNAL"
        advanced_market = "WAIT"
        advanced_confidence = 0

        if minute >= 70 and pressure_index >= 68 and momentum_score >= 65:
            advanced_signal = "LATE GOAL PRESSURE"
            advanced_market = "OVER / NEXT GOAL"
            advanced_confidence = 82
        elif minute >= 55 and total_goals <= 1 and tempo_score >= 60 and pressure_index >= 58:
            advanced_signal = "GOAL TEMPO BUILDUP"
            advanced_market = "OVER 1.5 / OVER 2.5"
            advanced_confidence = 76
        elif 25 <= minute <= 60 and shots_on_goal >= 3 and dangerous_attacks >= 35:
            advanced_signal = "BTTS PRESSURE"
            advanced_market = "BTTS LIVE"
            advanced_confidence = 72
        elif corners_per_min >= 0.12 and pressure_index >= 45:
            advanced_signal = "CORNERS PRESSURE"
            advanced_market = "CORNERS LIVE"
            advanced_confidence = 68

        live_edge = 0.0
        if odds:
            implied_probability = 1 / _to_float(odds, 1)
            model_probability = max(_to_float(base_confidence), advanced_confidence) / 100
            live_edge = round((model_probability - implied_probability) * 100, 2)

        return {
            "advanced_live_active": True,
            "shots_total": round(total_shots, 2),
            "shots_on_goal": round(shots_on_goal, 2),
            "dangerous_attacks": round(dangerous_attacks, 2),
            "attacks": round(attacks, 2),
            "corners": round(corners, 2),
            "possession_home": round(possession_home, 2),
            "possession_away": round(possession_away, 2),
            "shots_per_min": round(shots_per_min, 3),
            "shots_on_goal_per_min": round(shots_on_goal_per_min, 3),
            "dangerous_attacks_per_min": round(dangerous_attacks_per_min, 3),
            "attacks_per_min": round(attacks_per_min, 3),
            "corners_per_min": round(corners_per_min, 3),
            "tempo_score": round(tempo_score, 2),
            "pressure_index": round(pressure_index, 2),
            "momentum_score_adv": round(momentum_score, 2),
            "xg_pace": xg_pace,
            "live_intensity": live_intensity,
            "advanced_signal": advanced_signal,
            "advanced_market": advanced_market,
            "advanced_confidence": advanced_confidence,
            "live_edge": live_edge,
            "base_signal": base_signal,
            "base_confidence": base_confidence,
        }
