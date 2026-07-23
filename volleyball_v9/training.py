from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from .domain import VolleyballGame
from .model import VolleyballEloModel


TRAINING_SCHEMA_VERSION = "volleyball.training_dataset.v1"
CANDIDATE_SCHEMA_VERSION = "volleyball.elo_candidate.v1"
DEFAULT_HYPERPARAMETERS = {
    "base_rating": 1500.0,
    "home_advantage": 35.0,
    "k_factor": 24.0,
}


def canonical_json(payload: dict) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _eligible_games(games: Iterable[VolleyballGame]) -> list[VolleyballGame]:
    return sorted(
        (
            game
            for game in games
            if game.finished
            and game.home_sets is not None
            and game.away_sets is not None
            and game.home_sets != game.away_sets
            and game.home_team_id
            and game.away_team_id
            and game.home_team_id != game.away_team_id
            and game.scheduled_at
        ),
        key=lambda item: (item.scheduled_at, item.game_id),
    )


def build_training_dataset(games: Iterable[VolleyballGame]) -> dict:
    eligible = _eligible_games(games)
    rows = [
        {
            "away_sets": int(game.away_sets),
            "away_team_id": str(game.away_team_id),
            "game_id": str(game.game_id),
            "home_sets": int(game.home_sets),
            "home_team_id": str(game.home_team_id),
            "league_id": str(game.league_id),
            "scheduled_at": str(game.scheduled_at),
            "season": str(game.season),
        }
        for game in eligible
    ]
    document = {
        "schema_version": TRAINING_SCHEMA_VERSION,
        "sport": "volleyball",
        "label": "home_sets_gt_away_sets",
        "bookmaker_data_used": False,
        "post_match_fields": ["home_sets", "away_sets"],
        "row_count": len(rows),
        "first_scheduled_at": rows[0]["scheduled_at"] if rows else None,
        "last_scheduled_at": rows[-1]["scheduled_at"] if rows else None,
        "rows": rows,
    }
    serialized = canonical_json(document)
    return {
        "document": document,
        "canonical_json": serialized,
        "sha256": sha256_text(serialized),
        "games": eligible,
    }


@dataclass(frozen=True)
class CandidateBundle:
    status: str
    dataset_sha256: str
    dataset_rows: int
    minimum_rows: int
    dataset_document: dict | None = None
    artifact: dict | None = None
    artifact_sha256: str = ""
    candidate_id: str = ""
    reproducible: bool = False
    active_model_modified: bool = False

    def payload(self) -> dict:
        return {
            "status": self.status,
            "dataset_sha256": self.dataset_sha256,
            "dataset_rows": self.dataset_rows,
            "minimum_rows": self.minimum_rows,
            "dataset_document": self.dataset_document,
            "artifact": self.artifact,
            "artifact_sha256": self.artifact_sha256,
            "candidate_id": self.candidate_id,
            "reproducible": self.reproducible,
            "active_model_modified": self.active_model_modified,
        }


def _artifact(dataset: dict, games: list[VolleyballGame]) -> dict:
    parameters = dict(DEFAULT_HYPERPARAMETERS)
    model = VolleyballEloModel(**parameters)
    model.fit(games)
    return {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "sport": "volleyball",
        "registry_status": "CANDIDATE_ONLY",
        "shadow_only": True,
        "real_execution_allowed": False,
        "active_model_modified": False,
        "algorithm": "chronological_elo",
        "dataset": {
            "schema_version": TRAINING_SCHEMA_VERSION,
            "sha256": dataset["sha256"],
            "row_count": int(dataset["document"]["row_count"]),
            "first_scheduled_at": dataset["document"]["first_scheduled_at"],
            "last_scheduled_at": dataset["document"]["last_scheduled_at"],
        },
        "hyperparameters": parameters,
        "state": model.export_state(),
        "training_contract": {
            "chronological_order": True,
            "finished_matches_only": True,
            "bookmaker_odds_used": False,
            "candidate_not_activated": True,
            "validation_required_before_promotion": True,
        },
    }


def train_candidate(
    games: Iterable[VolleyballGame],
    *,
    minimum_rows: int,
) -> CandidateBundle:
    minimum = max(1, int(minimum_rows))
    dataset = build_training_dataset(games)
    row_count = int(dataset["document"]["row_count"])
    if row_count < minimum:
        return CandidateBundle(
            status="WAITING_MINIMUM_SAMPLE",
            dataset_sha256=dataset["sha256"],
            dataset_rows=row_count,
            minimum_rows=minimum,
        )
    artifact = _artifact(dataset, dataset["games"])
    artifact_json = canonical_json(artifact)
    artifact_sha256 = sha256_text(artifact_json)
    candidate_id = f"volleyball_candidate_{artifact_sha256[:24]}"
    first = CandidateBundle(
        status="CANDIDATE_READY",
        dataset_sha256=dataset["sha256"],
        dataset_rows=row_count,
        minimum_rows=minimum,
        dataset_document=dataset["document"],
        artifact=artifact,
        artifact_sha256=artifact_sha256,
        candidate_id=candidate_id,
        reproducible=False,
    )
    return CandidateBundle(
        **{
            **first.__dict__,
            "reproducible": verify_candidate(first),
        }
    )


def _games_from_dataset(document: dict) -> list[VolleyballGame]:
    games: list[VolleyballGame] = []
    for row in document.get("rows", []):
        games.append(
            VolleyballGame(
                game_id=str(row["game_id"]),
                scheduled_at=str(row["scheduled_at"]),
                status="FT",
                league_id=str(row.get("league_id", "")),
                league_name="",
                country="",
                season=str(row.get("season", "")),
                home_team_id=str(row["home_team_id"]),
                home_team="",
                away_team_id=str(row["away_team_id"]),
                away_team="",
                home_sets=int(row["home_sets"]),
                away_sets=int(row["away_sets"]),
                raw={},
            )
        )
    return games


def verify_candidate(bundle: CandidateBundle) -> bool:
    if bundle.dataset_document is None or bundle.artifact is None:
        return False
    dataset_json = canonical_json(bundle.dataset_document)
    if sha256_text(dataset_json) != bundle.dataset_sha256:
        return False
    regenerated_dataset = {
        "document": bundle.dataset_document,
        "sha256": bundle.dataset_sha256,
    }
    regenerated = _artifact(
        regenerated_dataset,
        _games_from_dataset(bundle.dataset_document),
    )
    regenerated_json = canonical_json(regenerated)
    return (
        regenerated == bundle.artifact
        and sha256_text(regenerated_json) == bundle.artifact_sha256
        and bundle.candidate_id
        == f"volleyball_candidate_{bundle.artifact_sha256[:24]}"
        and bundle.artifact.get("active_model_modified") is False
    )
