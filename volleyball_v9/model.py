from __future__ import annotations

import math
from collections.abc import Iterable

from .domain import ModelPrediction, VolleyballGame


class VolleyballEloModel:
    def __init__(self, *, base_rating: float = 1500.0, k_factor: float = 24.0, home_advantage: float = 35.0):
        self.base_rating = float(base_rating)
        self.k_factor = float(k_factor)
        self.home_advantage = float(home_advantage)
        self.ratings: dict[str, float] = {}
        self.matches: dict[str, int] = {}

    def _rating(self, team_id: str) -> float:
        return self.ratings.get(team_id, self.base_rating)

    def fit(self, games: Iterable[VolleyballGame]) -> None:
        ordered = sorted(games, key=lambda game: (game.scheduled_at, game.game_id))
        for game in ordered:
            if not game.finished or game.home_sets is None or game.away_sets is None:
                continue
            if game.home_sets == game.away_sets:
                continue
            home_rating = self._rating(game.home_team_id)
            away_rating = self._rating(game.away_team_id)
            expected_home = 1.0 / (
                1.0 + 10.0 ** ((away_rating - (home_rating + self.home_advantage)) / 400.0)
            )
            actual_home = 1.0 if game.home_sets > game.away_sets else 0.0
            set_margin = min(1.5, 1.0 + 0.1 * abs(game.home_sets - game.away_sets))
            delta = self.k_factor * set_margin * (actual_home - expected_home)
            self.ratings[game.home_team_id] = home_rating + delta
            self.ratings[game.away_team_id] = away_rating - delta
            self.matches[game.home_team_id] = self.matches.get(game.home_team_id, 0) + 1
            self.matches[game.away_team_id] = self.matches.get(game.away_team_id, 0) + 1

    def export_state(self) -> dict:
        return {
            "ratings": {
                key: round(float(value), 12)
                for key, value in sorted(self.ratings.items())
            },
            "matches": {
                key: int(value)
                for key, value in sorted(self.matches.items())
            },
        }

    def predict(self, home_team_id: str, away_team_id: str) -> ModelPrediction:
        home_rating = self._rating(home_team_id)
        away_rating = self._rating(away_team_id)
        probability = 1.0 / (
            1.0 + 10.0 ** ((away_rating - (home_rating + self.home_advantage)) / 400.0)
        )
        probability = min(0.97, max(0.03, probability))
        home_matches = self.matches.get(home_team_id, 0)
        away_matches = self.matches.get(away_team_id, 0)
        sample_factor = min(1.0, min(home_matches, away_matches) / 20.0)
        separation = min(1.0, abs(probability - 0.5) / 0.35)
        confidence = round(35.0 + 40.0 * sample_factor + 20.0 * separation, 2)
        return ModelPrediction(
            home_probability=round(probability, 8),
            away_probability=round(1.0 - probability, 8),
            home_fair_odds=round(1.0 / probability, 4),
            away_fair_odds=round(1.0 / (1.0 - probability), 4),
            home_rating=round(home_rating, 3),
            away_rating=round(away_rating, 3),
            home_matches=home_matches,
            away_matches=away_matches,
            confidence=confidence,
        )
