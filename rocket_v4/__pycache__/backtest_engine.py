from __future__ import annotations

from typing import Iterable, Dict, Any, List

from .orchestrator import RocketOrchestratorV4
from .settlement import SettlementEngineV4


class BacktestEngineV4:
    def __init__(self, orchestrator: RocketOrchestratorV4 | None = None):
        self.bot = orchestrator or RocketOrchestratorV4()
        self.settle = SettlementEngineV4()

    def run(self, rows: Iterable[Dict[str, Any]], market: str = "OVER_2_5") -> Dict[str, Any]:
        settled: List[Dict[str, Any]] = []
        for row in rows:
            odds = row.get("odds") or row.get("bookmaker_odds")
            pred = self.bot.analyze(row, market=market, bookmaker_odds=odds)
            if pred.get("status") != "ACCEPTED_VALUE":
                continue
            pred["stake"] = pred.get("stake", 1.0)
            if row.get("home_goals") is None or row.get("away_goals") is None:
                continue
            s = self.settle.settle_pick(pred, row)
            settled.append(s)
            self.bot.learn.update_from_settlement(s)
        profit = sum(float(x.get("profit", 0)) for x in settled)
        stake = sum(float(x.get("stake", 0)) for x in settled)
        wins = sum(1 for x in settled if x.get("status") == "WON")
        return {
            "bets": len(settled),
            "wins": wins,
            "losses": len(settled)-wins,
            "profit": round(profit, 4),
            "turnover": round(stake, 4),
            "roi": round(profit/stake, 6) if stake else 0.0,
            "hit_rate": round(wins/len(settled), 6) if settled else 0.0,
        }
