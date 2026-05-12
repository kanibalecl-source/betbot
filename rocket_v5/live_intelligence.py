from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict

from .utils import clamp, num


@dataclass
class LiveSignalV5:
    probability_adjustment: float
    home_xg_multiplier: float
    away_xg_multiplier: float
    risk_flag: str
    explanation: list[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LiveIntelligenceEngineV5:
    """Live context layer: red cards, momentum, pressure, substitutions, game state."""

    def evaluate(self, live: Dict[str, Any]) -> LiveSignalV5:
        minute = num(live.get("minute"), 0)
        home_red = num(live.get("home_red_cards"), 0)
        away_red = num(live.get("away_red_cards"), 0)
        h_momentum = num(live.get("home_momentum"), 0.0)
        a_momentum = num(live.get("away_momentum"), 0.0)
        h_pressure = num(live.get("home_pressure"), num(live.get("home_dangerous_attacks_last10"), 0.0))
        a_pressure = num(live.get("away_pressure"), num(live.get("away_dangerous_attacks_last10"), 0.0))
        h_goals = num(live.get("home_goals"), 0)
        a_goals = num(live.get("away_goals"), 0)

        hx = 1.0
        ax = 1.0
        explanation = []
        if home_red > away_red:
            hx *= 0.72; ax *= 1.22; explanation.append("home red-card disadvantage")
        if away_red > home_red:
            ax *= 0.72; hx *= 1.22; explanation.append("away red-card disadvantage")
        momentum_delta = clamp((h_momentum - a_momentum) / 100.0, -0.15, 0.15)
        pressure_delta = clamp((h_pressure - a_pressure) / 60.0, -0.10, 0.10)
        hx *= 1 + max(0.0, momentum_delta + pressure_delta)
        ax *= 1 + max(0.0, -momentum_delta - pressure_delta)

        game_state = h_goals - a_goals
        if minute > 70 and abs(game_state) >= 2:
            hx *= 0.86; ax *= 0.86; explanation.append("late two-goal state reduces intensity")
        elif minute > 70 and abs(game_state) == 1:
            trailing_home = game_state < 0
            if trailing_home: hx *= 1.12
            else: ax *= 1.12
            explanation.append("late one-goal state increases trailing-team pressure")
        adj = clamp((hx - ax) * 0.035, -0.06, 0.06)
        risk = "NORMAL"
        if minute < 10 or minute > 88:
            risk = "VOLATILE_TIME_WINDOW"
        if home_red or away_red:
            risk = "RED_CARD_VOLATILITY"
        return LiveSignalV5(round(adj, 6), round(hx, 4), round(ax, 4), risk, explanation)
