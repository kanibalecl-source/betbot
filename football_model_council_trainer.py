"""Leakage-safe trainer for the football model council shadow candidates."""
from __future__ import annotations

from collections import defaultdict
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from football_model_council import (
    COUNCIL_VERSION,
    CatBoostShadowAdapter,
    bivariate_poisson_score_matrix,
    normalize_market,
    poisson_score_matrix,
    probability_from_score_matrix,
)
from quality_upgrade_engine import DixonColesEngine, learn_stacking_weights


def _number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _target(value: Any) -> int | None:
    text = str("" if value is None else value).strip().upper()
    if text in {"1", "TRUE", "WIN", "WON"}:
        return 1
    if text in {"0", "FALSE", "LOSS", "LOST"}:
        return 0
    return None


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _metric(probabilities: list[float], targets: list[int]) -> dict[str, float]:
    if not targets:
        return {"samples": 0, "brier_score": 1.0, "log_loss": 99.0}
    clipped = [max(1e-6, min(1 - 1e-6, value)) for value in probabilities]
    brier = sum((value - target) ** 2 for value, target in zip(clipped, targets))
    loss = -sum(
        target * math.log(value) + (1 - target) * math.log(1 - value)
        for value, target in zip(clipped, targets)
    )
    return {
        "samples": len(targets),
        "brier_score": round(brier / len(targets), 8),
        "log_loss": round(loss / len(targets), 8),
    }


def _clean_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    clean = []
    for row in rows:
        sport = str(row.get("sport") or "football").strip().lower()
        if sport not in {"football", "soccer", "pilka_nozna", "piłka_nożna"}:
            continue
        target = _target(row.get("target"))
        home_xg = _number(row.get("home_xg"))
        away_xg = _number(row.get("away_xg"))
        champion = _number(row.get("current_probability"))
        market = normalize_market(row.get("market"))
        timestamp = str(row.get("timestamp") or "")
        if (
            target is None
            or home_xg is None
            or away_xg is None
            or champion is None
            or not market
            or not timestamp
        ):
            continue
        clean.append({
            **dict(row),
            "target": target,
            "home_xg": home_xg,
            "away_xg": away_xg,
            "current_probability": max(1e-6, min(1 - 1e-6, champion)),
            "market": market,
            "timestamp": timestamp,
        })
    return sorted(clean, key=lambda item: (item["timestamp"], str(item.get("record_id", ""))))


def _learn_bivariate_shared_rate(rows: list[dict[str, Any]]) -> tuple[float, dict[str, Any]]:
    candidates = (0.0, 0.04, 0.08, 0.12, 0.16, 0.20)
    reports = []
    for share in candidates:
        probabilities, targets = [], []
        for row in rows:
            shared = min(row["home_xg"], row["away_xg"]) * share
            probability = probability_from_score_matrix(
                bivariate_poisson_score_matrix(
                    row["home_xg"], row["away_xg"], shared_rate=shared
                ),
                row["market"],
            )
            if probability is not None:
                probabilities.append(probability)
                targets.append(row["target"])
        reports.append({
            "share": share,
            **_metric(probabilities, targets),
        })
    winner = min(reports, key=lambda item: (item["log_loss"], item["brier_score"]))
    # Runtime stores an absolute shared rate.  The population-average conversion
    # avoids inferring it from the future event currently being scored.
    mean_min_xg = sum(min(row["home_xg"], row["away_xg"]) for row in rows) / len(rows)
    return round(mean_min_xg * winner["share"], 8), {
        "selection": "past_only_grid_log_loss",
        "winning_share": winner["share"],
        "candidates": reports,
    }


def _hierarchical_state(rows: list[dict[str, Any]]) -> dict[str, Any]:
    league_values: dict[str, list[tuple[float, float]]] = defaultdict(list)
    home_values: dict[str, list[float]] = defaultdict(list)
    away_values: dict[str, list[float]] = defaultdict(list)
    seen_fixtures: set[str] = set()
    unique = []
    for row in rows:
        fixture = str(row.get("fixture_id") or "")
        identity = fixture or "|".join((
            str(row.get("timestamp") or ""),
            str(row.get("home_team") or ""),
            str(row.get("away_team") or ""),
        ))
        if identity in seen_fixtures:
            continue
        seen_fixtures.add(identity)
        unique.append(row)
    for row in unique:
        league = str(row.get("league") or "UNKNOWN")
        home_team = str(row.get("home_team") or "UNKNOWN")
        away_team = str(row.get("away_team") or "UNKNOWN")
        league_values[league].append((row["home_xg"], row["away_xg"]))
        if home_team != "UNKNOWN":
            home_values[home_team].append(row["home_xg"])
        if away_team != "UNKNOWN":
            away_values[away_team].append(row["away_xg"])
    global_home = sum(row["home_xg"] for row in unique) / len(unique)
    global_away = sum(row["away_xg"] for row in unique) / len(unique)
    leagues = {
        league: {
            "home_rate": round(sum(home for home, _ in values) / len(values), 8),
            "away_rate": round(sum(away for _, away in values) / len(values), 8),
            "samples": len(values),
        }
        for league, values in league_values.items()
        if len(values) >= 12
    }
    teams: dict[str, dict[str, Any]] = {}
    for team in set(home_values) | set(away_values):
        payload: dict[str, Any] = {}
        if len(home_values.get(team, ())) >= 5:
            payload["home_rate"] = round(
                sum(home_values[team]) / len(home_values[team]), 8
            )
            payload["home_samples"] = len(home_values[team])
        if len(away_values.get(team, ())) >= 5:
            payload["away_rate"] = round(
                sum(away_values[team]) / len(away_values[team]), 8
            )
            payload["away_samples"] = len(away_values[team])
        if payload:
            teams[team] = payload
    return {
        "global_prior": {
            "home_rate": round(global_home, 8),
            "away_rate": round(global_away, 8),
            "samples": len(unique),
        },
        "league_priors": leagues,
        "team_priors": teams,
        "hierarchical_prior_strength": 6.0,
        "hierarchical_unique_fixtures": len(unique),
    }


def _catboost_matrix(rows: list[dict[str, Any]]) -> list[list[Any]]:
    ordered = (
        CatBoostShadowAdapter.NUMERIC_FEATURES
        + CatBoostShadowAdapter.CATEGORICAL_FEATURES
    )
    matrix = []
    for row in rows:
        values = []
        for name in ordered:
            if name in CatBoostShadowAdapter.CATEGORICAL_FEATURES:
                values.append(str(row.get(name) or "UNKNOWN"))
            else:
                number = _number(row.get(name))
                values.append(float("nan") if number is None else number)
        matrix.append(values)
    return matrix


def _train_catboost(
    train: list[dict[str, Any]],
    validation: list[dict[str, Any]],
    test: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    try:
        from catboost import CatBoostClassifier
    except Exception as exc:
        return {
            "validation_status": "WAITING_DEPENDENCY",
            "reason": f"catboost_import:{type(exc).__name__}",
        }
    categorical = list(range(
        len(CatBoostShadowAdapter.NUMERIC_FEATURES),
        len(CatBoostShadowAdapter.NUMERIC_FEATURES)
        + len(CatBoostShadowAdapter.CATEGORICAL_FEATURES),
    ))
    model = CatBoostClassifier(
        iterations=int(os.getenv("BETBOT_COUNCIL_CATBOOST_ITERATIONS", "350")),
        depth=int(os.getenv("BETBOT_COUNCIL_CATBOOST_DEPTH", "6")),
        learning_rate=float(os.getenv("BETBOT_COUNCIL_CATBOOST_LEARNING_RATE", "0.035")),
        loss_function="Logloss",
        eval_metric="Logloss",
        random_seed=1701,
        l2_leaf_reg=6.0,
        random_strength=0.5,
        verbose=False,
        allow_writing_files=False,
        thread_count=max(1, int(os.getenv("BETBOT_COUNCIL_CATBOOST_THREADS", "2"))),
    )
    model.fit(
        _catboost_matrix(train),
        [row["target"] for row in train],
        cat_features=categorical,
        eval_set=(
            _catboost_matrix(validation),
            [row["target"] for row in validation],
        ),
        early_stopping_rounds=40,
        verbose=False,
    )
    challenger = [
        float(value[1]) for value in model.predict_proba(_catboost_matrix(test))
    ]
    targets = [row["target"] for row in test]
    champion_metrics = _metric(
        [row["current_probability"] for row in test], targets
    )
    challenger_metrics = _metric(challenger, targets)
    brier_gain = champion_metrics["brier_score"] - challenger_metrics["brier_score"]
    log_gain = champion_metrics["log_loss"] - challenger_metrics["log_loss"]
    validated = (
        brier_gain >= float(os.getenv("BETBOT_COUNCIL_MIN_BRIER_GAIN", "0.0002"))
        and log_gain >= float(os.getenv("BETBOT_COUNCIL_MIN_LOGLOSS_GAIN", "0.0002"))
    )
    artifact = output_dir / "catboost_shadow_candidate.cbm"
    model.save_model(str(artifact))
    return {
        "validation_status": (
            "SHADOW_VALIDATED" if validated else "SHADOW_REJECTED"
        ),
        "artifact_path": artifact.name,
        "train_samples": len(train),
        "early_stopping_samples": len(validation),
        "test_samples": len(test),
        "chronological_three_way_split": True,
        "bookmaker_odds_used_as_feature": False,
        "champion_metrics": champion_metrics,
        "challenger_metrics": challenger_metrics,
        "brier_gain": round(brier_gain, 8),
        "log_loss_gain": round(log_gain, 8),
        "_weight_predictions": [
            float(value[1])
            for value in model.predict_proba(_catboost_matrix(validation))
        ],
    }


def _learn_diagnostic_weights(
    rows: list[dict[str, Any]],
    *,
    shared_rate: float,
    hierarchy: Mapping[str, Any],
    catboost_predictions: list[float] | None = None,
) -> dict[str, float]:
    """Fit simplex weights on a past chronological calibration window."""
    predictions: list[list[float]] = []
    targets: list[int] = []
    global_prior = hierarchy.get("global_prior", {})
    leagues = hierarchy.get("league_priors", {})
    prior_strength = float(hierarchy.get("hierarchical_prior_strength", 6.0))
    include_catboost = (
        catboost_predictions is not None
        and len(catboost_predictions) == len(rows)
    )
    for row_index, row in enumerate(rows):
        poisson = probability_from_score_matrix(
            poisson_score_matrix(row["home_xg"], row["away_xg"]),
            row["market"],
        )
        dixon = DixonColesEngine(max_goals=12).predict_market(
            row["market"], row["home_xg"], row["away_xg"]
        )
        bivariate = probability_from_score_matrix(
            bivariate_poisson_score_matrix(
                row["home_xg"], row["away_xg"], shared_rate=shared_rate
            ),
            row["market"],
        )
        league_prior = (
            leagues.get(str(row.get("league") or "UNKNOWN"), {})
            if isinstance(leagues, Mapping)
            else {}
        )
        prior_home = _number(
            league_prior.get("home_rate")
            if isinstance(league_prior, Mapping)
            else None
        ) or _number(
            global_prior.get("home_rate")
            if isinstance(global_prior, Mapping)
            else None
        ) or 1.45
        prior_away = _number(
            league_prior.get("away_rate")
            if isinstance(league_prior, Mapping)
            else None
        ) or _number(
            global_prior.get("away_rate")
            if isinstance(global_prior, Mapping)
            else None
        ) or 1.15
        evidence = 8.0
        hierarchical_home = (
            row["home_xg"] * evidence + prior_home * prior_strength
        ) / (evidence + prior_strength)
        hierarchical_away = (
            row["away_xg"] * evidence + prior_away * prior_strength
        ) / (evidence + prior_strength)
        hierarchical = probability_from_score_matrix(
            poisson_score_matrix(hierarchical_home, hierarchical_away),
            row["market"],
        )
        values = [
            row["current_probability"],
            poisson,
            dixon,
            bivariate,
        ]
        if include_catboost:
            values.append(catboost_predictions[row_index])
        values.append(hierarchical)
        if any(value is None for value in values):
            continue
        predictions.append([float(value) for value in values])
        targets.append(row["target"])
    names = [
        "champion",
        "poisson",
        "dixon_coles",
        "bivariate_poisson",
    ]
    if include_catboost:
        names.append("catboost")
    names.append("hierarchical_bayes")
    if len(predictions) < 40:
        return {
            "champion": 0.40,
            "poisson": 0.15,
            "dixon_coles": 0.15,
            "bivariate_poisson": 0.15,
            "catboost": 0.0,
            "hierarchical_bayes": 0.15,
        }
    weights = learn_stacking_weights(predictions, targets)
    result = {name: weight for name, weight in zip(names, weights)}
    result.setdefault("catboost", 0.0)
    return result


def train_football_council_shadow(
    rows: Iterable[Mapping[str, Any]],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Create shadow state only; never changes any active model registry."""
    clean = _clean_rows(rows)
    minimum = max(100, int(os.getenv("BETBOT_COUNCIL_MIN_TRAINING_ROWS", "500")))
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    if len(clean) < minimum:
        result = {
            "version": COUNCIL_VERSION,
            "status": "WAITING_FOR_SETTLED_DATA",
            "samples": len(clean),
            "required_samples": minimum,
            "active_model_modified": False,
        }
        _atomic_json(target_dir / "training_status.json", result)
        return result
    split = max(20, int(len(clean) * 0.15))
    train = clean[: -2 * split]
    validation = clean[-2 * split: -split]
    test = clean[-split:]
    if len(train) < 60:
        result = {
            "version": COUNCIL_VERSION,
            "status": "WAITING_FOR_CHRONOLOGICAL_PARTITIONS",
            "samples": len(clean),
            "required_samples": max(minimum, 100),
            "active_model_modified": False,
        }
        _atomic_json(target_dir / "training_status.json", result)
        return result
    shared_rate, bivariate_validation = _learn_bivariate_shared_rate(train)
    hierarchy = _hierarchical_state(train)
    catboost = _train_catboost(train, validation, test, target_dir)
    catboost_predictions = catboost.pop("_weight_predictions", None)
    diagnostic_weights = _learn_diagnostic_weights(
        validation,
        shared_rate=shared_rate,
        hierarchy=hierarchy,
        catboost_predictions=(
            catboost_predictions
            if catboost.get("validation_status") == "SHADOW_VALIDATED"
            else None
        ),
    )
    state = {
        "version": COUNCIL_VERSION,
        "status": "SHADOW_STATE_READY",
        "mode": "SHADOW_ONLY",
        "champion_remains_active": True,
        "challengers_have_decision_authority": False,
        "active_model_modified": False,
        "bookmaker_odds_used_as_model_feature": False,
        "training_samples": len(train),
        "calibration_samples": len(validation),
        "validation_samples": len(test),
        "bivariate_shared_rate": shared_rate,
        "bivariate_validation": bivariate_validation,
        "diagnostic_weights": diagnostic_weights,
        "diagnostic_weights_method": (
            "non_negative_simplex_log_loss_on_chronological_calibration_window"
        ),
        **hierarchy,
        "catboost": catboost,
    }
    _atomic_json(target_dir / "shadow_state.json", state)
    _atomic_json(target_dir / "training_status.json", {
        "status": "SHADOW_STATE_READY",
        "samples": len(clean),
        "catboost_validation": catboost.get("validation_status"),
        "active_model_modified": False,
    })
    return state
