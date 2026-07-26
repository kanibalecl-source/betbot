from __future__ import annotations

import math
from collections.abc import Iterable

from .domain import ModelPrediction, VolleyballGame


class VolleyballEloModel:
    """Chronological Elo + set-strength ensemble.

    The set component uses only matches already finished at prediction time.
    ``form_weight=0`` reproduces the legacy Elo champion exactly, which makes
    the richer model safe to evaluate as a challenger.
    """

    def __init__(
        self,
        *,
        base_rating: float = 1500.0,
        k_factor: float = 24.0,
        home_advantage: float = 35.0,
        form_weight: float = 0.0,
        calibration_temperature: float = 1.0,
    ):
        self.base_rating = float(base_rating)
        self.k_factor = float(k_factor)
        self.home_advantage = float(home_advantage)
        self.form_weight = min(0.45, max(0.0, float(form_weight)))
        self.calibration_temperature = min(
            2.0, max(0.5, float(calibration_temperature))
        )
        self.ratings: dict[str, float] = {}
        self.matches: dict[str, int] = {}
        self.sets_for: dict[str, int] = {}
        self.sets_against: dict[str, int] = {}

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
            self.sets_for[game.home_team_id] = self.sets_for.get(game.home_team_id, 0) + int(game.home_sets)
            self.sets_against[game.home_team_id] = self.sets_against.get(game.home_team_id, 0) + int(game.away_sets)
            self.sets_for[game.away_team_id] = self.sets_for.get(game.away_team_id, 0) + int(game.away_sets)
            self.sets_against[game.away_team_id] = self.sets_against.get(game.away_team_id, 0) + int(game.home_sets)

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
            "sets_for": {key: int(value) for key, value in sorted(self.sets_for.items())},
            "sets_against": {
                key: int(value) for key, value in sorted(self.sets_against.items())
            },
        }

    def _set_strength(self, team_id: str) -> float:
        # Beta smoothing prevents tiny samples from producing extreme values.
        won = float(self.sets_for.get(team_id, 0))
        lost = float(self.sets_against.get(team_id, 0))
        return (won + 3.0) / (won + lost + 6.0)

    def predict(self, home_team_id: str, away_team_id: str) -> ModelPrediction:
        home_rating = self._rating(home_team_id)
        away_rating = self._rating(away_team_id)
        elo_probability = 1.0 / (
            1.0 + 10.0 ** ((away_rating - (home_rating + self.home_advantage)) / 400.0)
        )
        home_form = self._set_strength(home_team_id)
        away_form = self._set_strength(away_team_id)
        # Difference in smoothed set share is mapped to a conservative
        # probability and gradually enabled as both samples mature.
        form_probability = 1.0 / (
            1.0 + math.exp(-5.0 * (home_form - away_form + 0.025))
        )
        home_matches = self.matches.get(home_team_id, 0)
        away_matches = self.matches.get(away_team_id, 0)
        maturity = min(1.0, min(home_matches, away_matches) / 12.0)
        effective_weight = self.form_weight * maturity
        probability = (
            (1.0 - effective_weight) * elo_probability
            + effective_weight * form_probability
        )
        raw_probability = min(1.0 - 1e-9, max(1e-9, probability))
        probability = 1.0 / (
            1.0
            + math.exp(
                -math.log(raw_probability / (1.0 - raw_probability))
                / self.calibration_temperature
            )
        )
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
            form_probability=round(form_probability, 8),
            feature_quality=round(maturity, 8),
        )
