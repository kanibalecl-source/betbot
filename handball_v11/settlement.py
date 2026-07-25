from __future__ import annotations

from .domain import FINISHED_STATUSES, VOID_STATUSES, HandballGame


def settle_match_winner(outcome: str, game: HandballGame) -> str:
    status = game.status.upper()
    if status in VOID_STATUSES:
        return "VOID"
    if status not in FINISHED_STATUSES:
        return "PENDING"
    if game.home_goals is None or game.away_goals is None:
        return "REVIEW"
    if game.home_goals == game.away_goals:
        # A verified two-way no-draw offer cannot be graded as a loss on a
        # tied final score. Close it neutrally and keep it out of training.
        return "VOID"
    winner = "HOME" if game.home_goals > game.away_goals else "AWAY"
    return "WON" if outcome.upper() == winner else "LOST"


def profit_for_result(result: str, odds: float, stake: float = 1.0) -> float:
    if result == "WON":
        return round(stake * (odds - 1.0), 6)
    if result == "LOST":
        return round(-stake, 6)
    return 0.0


