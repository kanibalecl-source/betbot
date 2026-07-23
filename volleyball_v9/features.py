from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .domain import ModelPrediction, VolleyballGame
from .model import VolleyballEloModel


FEATURE_SCHEMA_VERSION = "volleyball.point_in_time.v1"


class FeatureLeakageError(ValueError):
    pass


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class PointInTimeFeatures:
    prediction: ModelPrediction
    payload: dict


def build_point_in_time_features(
    target: VolleyballGame,
    training_games: Iterable[VolleyballGame],
    *,
    observed_at: str,
    model_version: str,
    source_metadata: dict,
) -> PointInTimeFeatures:
    observed = parse_utc(observed_at)
    scheduled = parse_utc(target.scheduled_at)
    if observed >= scheduled:
        raise FeatureLeakageError("feature_observed_at_not_before_match")

    eligible = list(training_games)
    for source in eligible:
        if parse_utc(source.scheduled_at) >= observed:
            raise FeatureLeakageError("source_game_not_before_feature_cutoff")

    model = VolleyballEloModel()
    model.fit(eligible)
    prediction = model.predict(target.home_team_id, target.away_team_id)
    payload = {
        "feature_schema": FEATURE_SCHEMA_VERSION,
        "model_version": model_version,
        "game_id": target.game_id,
        "scheduled_at": target.scheduled_at,
        "observed_at": observed_at,
        "feature_cutoff_at": observed_at,
        "home_team_id": target.home_team_id,
        "away_team_id": target.away_team_id,
        "home_rating": prediction.home_rating,
        "away_rating": prediction.away_rating,
        "home_matches": prediction.home_matches,
        "away_matches": prediction.away_matches,
        "home_probability": prediction.home_probability,
        "away_probability": prediction.away_probability,
        "home_fair_odds": prediction.home_fair_odds,
        "away_fair_odds": prediction.away_fair_odds,
        "confidence": prediction.confidence,
        "source_games": int(source_metadata.get("source_games", len(eligible))),
        "source_max_scheduled_at": source_metadata.get("source_max_scheduled_at"),
        "source_max_observed_at": source_metadata.get("source_max_observed_at"),
        "leakage_status": "PASS",
    }
    return PointInTimeFeatures(prediction=prediction, payload=payload)
