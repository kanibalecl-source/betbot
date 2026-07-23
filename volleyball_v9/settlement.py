from __future__ import annotations

from .domain import FINISHED_STATUSES, VOID_STATUSES, VolleyballGame


def settle_match_winner(outcome: str, game: VolleyballGame) -> str:
    status = game.status.upper()
    if status in VOID_STATUSES:
        return "VOID"
    if status not in FINISHED_STATUSES:
        return "PENDING"
    if game.home_sets is None or game.away_sets is None:
        return "REVIEW"
    if game.home_sets == game.away_sets:
        return "REVIEW"
    winner = "HOME" if game.home_sets > game.away_sets else "AWAY"
    return "WON" if outcome.upper() == winner else "LOST"


def profit_for_result(result: str, odds: float, stake: float = 1.0) -> float:
    if result == "WON":
        return round(stake * (odds - 1.0), 6)
    if result == "LOST":
        return round(-stake, 6)
    return 0.0

