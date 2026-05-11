"""Settlement engine for automatic feedback loop."""
from __future__ import annotations

from typing import Dict


class SettlementEngineV3:
    def settle(self, market: str, home_goals: int, away_goals: int) -> str:
        market = str(market).upper().replace('.', '_')
        hg, ag = int(home_goals), int(away_goals)
        total = hg + ag
        rules = {
            'HOME_WIN': hg > ag,
            'DRAW': hg == ag,
            'AWAY_WIN': ag > hg,
            'HOME_OR_DRAW': hg >= ag,
            'AWAY_OR_DRAW': ag >= hg,
            'HOME_OR_AWAY': hg != ag,
            'BTTS_YES': hg > 0 and ag > 0,
            'BTTS_NO': hg == 0 or ag == 0,
        }
        if market in rules:
            return 'WIN' if rules[market] else 'LOSE'
        if market.startswith('OVER_'):
            line = float(market.replace('OVER_', '').replace('_', '.'))
            return 'WIN' if total > line else 'LOSE'
        if market.startswith('UNDER_'):
            line = float(market.replace('UNDER_', '').replace('_', '.'))
            return 'WIN' if total < line else 'LOSE'
        return 'UNKNOWN'

    def pnl(self, settlement: str, stake: float, odds: float) -> float:
        settlement = str(settlement).upper()
        stake = float(stake or 0)
        odds = float(odds or 0)
        if settlement == 'WIN':
            return round(stake * (odds - 1), 2)
        if settlement == 'LOSE':
            return round(-stake, 2)
        return 0.0

    def record(self, pick: Dict, home_goals: int, away_goals: int) -> Dict:
        market = pick.get('market') or pick.get('kod_rynku') or pick.get('pick')
        settlement = self.settle(market, home_goals, away_goals)
        stake = pick.get('stake') or pick.get('stawka_pln') or 0
        odds = pick.get('bookmaker_odds') or pick.get('kurs_buk') or pick.get('odds') or 0
        out = dict(pick)
        out.update({
            'home_goals': int(home_goals),
            'away_goals': int(away_goals),
            'result_score': f'{home_goals}:{away_goals}',
            'settlement': settlement,
            'profit': self.pnl(settlement, stake, odds),
        })
        return out
