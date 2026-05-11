from __future__ import annotations

from typing import Dict, Any


class RiskEngineV4:
    def __init__(self, bankroll: float = 1000.0, fractional_kelly: float = 0.20, max_single_stake_pct: float = 0.015):
        self.bankroll = float(bankroll)
        self.fractional_kelly = float(fractional_kelly)
        self.max_single_stake_pct = float(max_single_stake_pct)

    def stake(self, probability: float, odds: float, data_quality: float = 1.0) -> Dict[str, Any]:
        p = float(probability)
        b = float(odds) - 1.0
        q = 1.0 - p
        if b <= 0:
            return {"stake": 0.0, "kelly_fraction": 0.0, "reason": "BAD_ODDS"}
        kelly = max(0.0, (b*p - q) / b)
        quality_mult = max(0.25, min(1.0, float(data_quality)))
        fraction = min(kelly * self.fractional_kelly * quality_mult, self.max_single_stake_pct)
        return {"stake": round(self.bankroll * fraction, 2), "kelly_fraction": round(kelly, 6), "stake_fraction": round(fraction, 6)}
