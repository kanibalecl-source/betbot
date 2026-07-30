from __future__ import annotations

from .domain import FINISHED_STATUSES, VOID_STATUSES, BasketballGame


def settle_game(game: BasketballGame) -> dict[str, object]:
    status = game.status.upper()
    if status in VOID_STATUSES:
        return {"status": "VOID", "winner": "", "total_points": None}
    if status not in FINISHED_STATUSES:
        return {"status": "PENDING", "winner": "", "total_points": None}
    if game.home_score is None or game.away_score is None:
        return {"status": "REVIEW", "winner": "", "total_points": None}
    if game.home_score < 0 or game.away_score < 0:
        return {"status": "REVIEW", "winner": "", "total_points": None}
    if game.home_score == game.away_score:
        # A final basketball score cannot remain tied. Never train on it.
        return {"status": "REVIEW", "winner": "", "total_points": None}
    return {
        "status": "SETTLED",
        "winner": "HOME" if game.home_score > game.away_score else "AWAY",
        "total_points": game.home_score + game.away_score,
        "margin": abs(game.home_score - game.away_score),
        "overtime": game.overtime,
    }

