from __future__ import annotations

from typing import Dict, Any


def settle_market(market: str, home_goals: int, away_goals: int) -> bool | None:
    market = str(market).upper().replace('.', '_')
    total = int(home_goals) + int(away_goals)
    if market == "HOME_WIN": return home_goals > away_goals
    if market == "DRAW": return home_goals == away_goals
    if market == "AWAY_WIN": return away_goals > home_goals
    if market == "HOME_OR_DRAW": return home_goals >= away_goals
    if market == "AWAY_OR_DRAW": return away_goals >= home_goals
    if market == "HOME_OR_AWAY": return home_goals != away_goals
    if market == "BTTS_YES": return home_goals > 0 and away_goals > 0
    if market == "BTTS_NO": return home_goals == 0 or away_goals == 0
    for line in [0.5, 1.5, 2.5, 3.5, 4.5]:
        key = str(line).replace('.', '_')
        if market == f"OVER_{key}": return total > line
        if market == f"UNDER_{key}": return total < line
    return None


class SettlementEngineV4:
    def settle_pick(self, pick: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        hg = int(result.get("home_goals"))
        ag = int(result.get("away_goals"))
        won = settle_market(pick.get("market"), hg, ag)
        out = dict(pick)
        out["result_score"] = f"{hg}:{ag}"
        if won is None:
            out["status"] = "UNSUPPORTED_SETTLEMENT"
            out["profit"] = 0.0
            return out
        stake = float(pick.get("stake", 1.0) or 1.0)
        odds = float(pick.get("bookmaker_odds", pick.get("odds", 1.0)) or 1.0)
        out["won"] = won
        out["status"] = "WON" if won else "LOST"
        out["profit"] = round(stake * (odds - 1.0), 4) if won else round(-stake, 4)
        return out
