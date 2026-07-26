from __future__ import annotations

import math
from collections.abc import Iterable

from .domain import ModelPrediction, HandballGame


class HandballEloModel:
    """Time-safe Elo + goal-strength ensemble.

    Draws update team strength with a neutral Elo target instead of being
    discarded.  Published two-way probabilities remain conditional on a
    non-draw result; explicit 1X2 probabilities are exposed for shadow
    collection and later independent validation.
    """

    def __init__(
        self,
        *,
        base_rating: float = 1500.0,
        k_factor: float = 24.0,
        home_advantage: float = 35.0,
        form_weight: float = 0.0,
        draw_prior: float = 0.08,
        calibration_temperature: float = 1.0,
    ):
        self.base_rating = float(base_rating)
        self.k_factor = float(k_factor)
        self.home_advantage = float(home_advantage)
        self.form_weight = min(0.45, max(0.0, float(form_weight)))
        self.draw_prior = min(0.25, max(0.01, float(draw_prior)))
        self.calibration_temperature = min(
            2.0, max(0.5, float(calibration_temperature))
        )
        self.ratings: dict[str, float] = {}
        self.matches: dict[str, int] = {}
        self.goals_for: dict[str, int] = {}
        self.goals_against: dict[str, int] = {}
        self.draws = 0
        self.total_games = 0

    def _rating(self, team_id: str) -> float:
        return self.ratings.get(team_id, self.base_rating)

    def fit(self, games: Iterable[HandballGame]) -> None:
        ordered = sorted(games, key=lambda game: (game.scheduled_at, game.game_id))
        for game in ordered:
            if not game.finished or game.home_goals is None or game.away_goals is None:
                continue
            home_rating = self._rating(game.home_team_id)
            away_rating = self._rating(game.away_team_id)
            expected_home = 1.0 / (
                1.0 + 10.0 ** ((away_rating - (home_rating + self.home_advantage)) / 400.0)
            )
            actual_home = (
                1.0
                if game.home_goals > game.away_goals
                else 0.0 if game.home_goals < game.away_goals else 0.5
            )
            goal_margin = min(
                1.75,
                1.0 + 0.05 * abs(game.home_goals - game.away_goals),
            )
            delta = self.k_factor * goal_margin * (actual_home - expected_home)
            self.ratings[game.home_team_id] = home_rating + delta
            self.ratings[game.away_team_id] = away_rating - delta
            self.matches[game.home_team_id] = self.matches.get(game.home_team_id, 0) + 1
            self.matches[game.away_team_id] = self.matches.get(game.away_team_id, 0) + 1
            self.goals_for[game.home_team_id] = self.goals_for.get(game.home_team_id, 0) + int(game.home_goals)
            self.goals_against[game.home_team_id] = self.goals_against.get(game.home_team_id, 0) + int(game.away_goals)
            self.goals_for[game.away_team_id] = self.goals_for.get(game.away_team_id, 0) + int(game.away_goals)
            self.goals_against[game.away_team_id] = self.goals_against.get(game.away_team_id, 0) + int(game.home_goals)
            self.total_games += 1
            self.draws += int(game.home_goals == game.away_goals)

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
            "goals_for": {key: int(value) for key, value in sorted(self.goals_for.items())},
            "goals_against": {
                key: int(value) for key, value in sorted(self.goals_against.items())
            },
            "draws": self.draws,
            "total_games": self.total_games,
        }

    def _net_goals(self, team_id: str) -> float:
        games = self.matches.get(team_id, 0)
        if not games:
            return 0.0
        return (
            self.goals_for.get(team_id, 0)
            - self.goals_against.get(team_id, 0)
        ) / games

    def predict(self, home_team_id: str, away_team_id: str) -> ModelPrediction:
        home_rating = self._rating(home_team_id)
        away_rating = self._rating(away_team_id)
        elo_probability = 1.0 / (
            1.0 + 10.0 ** ((away_rating - (home_rating + self.home_advantage)) / 400.0)
        )
        home_matches = self.matches.get(home_team_id, 0)
        away_matches = self.matches.get(away_team_id, 0)
        net_difference = self._net_goals(home_team_id) - self._net_goals(away_team_id)
        goal_form_probability = 1.0 / (
            1.0 + math.exp(-max(-12.0, min(12.0, 0.32 * net_difference + 0.10)))
        )
        maturity = min(1.0, min(home_matches, away_matches) / 15.0)
        effective_weight = self.form_weight * maturity
        conditional_home = (
            (1.0 - effective_weight) * elo_probability
            + effective_weight * goal_form_probability
        )
        raw_conditional = min(1.0 - 1e-9, max(1e-9, conditional_home))
        conditional_home = 1.0 / (
            1.0
            + math.exp(
                -math.log(raw_conditional / (1.0 - raw_conditional))
                / self.calibration_temperature
            )
        )
        # Draw probability is higher for evenly matched teams.  The empirical
        # rate is shrunk strongly to a sport prior to avoid small-sample noise.
        empirical_draw = (
            (self.draws + 8.0 * self.draw_prior) / (self.total_games + 8.0)
        )
        closeness = 1.0 - min(1.0, abs(conditional_home - 0.5) / 0.5)
        draw_probability = min(
            0.25,
            max(0.01, empirical_draw * (0.65 + 0.35 * closeness)),
        )
        probability = conditional_home
        probability = min(0.97, max(0.03, probability))
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
            elo_probability=round(elo_probability, 8),
            goal_form_probability=round(goal_form_probability, 8),
            draw_probability=round(draw_probability, 8),
            home_1x2_probability=round(probability * (1.0 - draw_probability), 8),
            away_1x2_probability=round((1.0 - probability) * (1.0 - draw_probability), 8),
            feature_quality=round(maturity, 8),
        )

