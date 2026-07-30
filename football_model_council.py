"""Football model council evaluated strictly in shadow mode.

The active production probability (``champion_probability``) is immutable in
this module.  Every challenger predicts the exact same selected market and the
returned consensus is diagnostic evidence only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
from statistics import pstdev
from typing import Any, Mapping

from quality_upgrade_engine import DixonColesEngine
from storage_paths import get_data_dir


COUNCIL_VERSION = "football_model_council_v17"
MODEL_ORDER = (
    "champion",
    "poisson",
    "dixon_coles",
    "bivariate_poisson",
    "catboost",
    "hierarchical_bayes",
)
DEFAULT_WEIGHTS = {
    "champion": 0.40,
    "poisson": 0.12,
    "dixon_coles": 0.14,
    "bivariate_poisson": 0.14,
    "catboost": 0.10,
    "hierarchical_bayes": 0.10,
}
_ALIASES = {
    "1": "HOME_WIN",
    "HOME": "HOME_WIN",
    "X": "DRAW",
    "2": "AWAY_WIN",
    "AWAY": "AWAY_WIN",
    "1X": "DOUBLE_1X",
    "HOME_OR_DRAW": "DOUBLE_1X",
    "X2": "DOUBLE_X2",
    "AWAY_OR_DRAW": "DOUBLE_X2",
    "12": "DOUBLE_12",
    "HOME_OR_AWAY": "DOUBLE_12",
    "OVER_05": "OVER_0_5",
    "UNDER_05": "UNDER_0_5",
    "OVER_15": "OVER_1_5",
    "UNDER_15": "UNDER_1_5",
    "OVER_25": "OVER_2_5",
    "UNDER_25": "UNDER_2_5",
    "OVER_35": "OVER_3_5",
    "UNDER_35": "UNDER_3_5",
    "OVER_45": "OVER_4_5",
    "UNDER_45": "UNDER_4_5",
}


def _number(value: Any) -> float | None:
    try:
        result = float(str(value).replace(",", ".").replace("%", "").strip())
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _probability(value: Any) -> float | None:
    result = _number(value)
    if result is None:
        return None
    if result > 1.0:
        result /= 100.0
    if not 0.0 < result < 1.0:
        return None
    return result


def normalize_market(market: Any) -> str:
    key = (
        str(market or "")
        .strip()
        .upper()
        .replace(".", "_")
        .replace("-", "_")
        .replace(" ", "_")
    )
    return _ALIASES.get(key, key)


def poisson_score_matrix(
    home_rate: float,
    away_rate: float,
    *,
    max_goals: int = 12,
) -> dict[tuple[int, int], float]:
    """Independent Poisson score distribution with normalized truncated tail."""
    home_rate = max(0.01, float(home_rate))
    away_rate = max(0.01, float(away_rate))
    home_terms = [math.exp(-home_rate)]
    away_terms = [math.exp(-away_rate)]
    for goals in range(1, max_goals + 1):
        home_terms.append(home_terms[-1] * home_rate / goals)
        away_terms.append(away_terms[-1] * away_rate / goals)
    matrix = {
        (home, away): home_terms[home] * away_terms[away]
        for home in range(max_goals + 1)
        for away in range(max_goals + 1)
    }
    mass = sum(matrix.values())
    return {score: value / mass for score, value in matrix.items()}


def bivariate_poisson_score_matrix(
    home_rate: float,
    away_rate: float,
    *,
    shared_rate: float,
    max_goals: int = 12,
) -> dict[tuple[int, int], float]:
    """Bivariate Poisson using X=U1+U3 and Y=U2+U3.

    ``home_rate`` and ``away_rate`` remain the marginal scoring means.
    """
    home_rate = max(0.01, float(home_rate))
    away_rate = max(0.01, float(away_rate))
    shared = max(0.0, min(float(shared_rate), min(home_rate, away_rate) * 0.80))
    home_independent = max(1e-9, home_rate - shared)
    away_independent = max(1e-9, away_rate - shared)
    common = math.exp(-(home_independent + away_independent + shared))
    matrix: dict[tuple[int, int], float] = {}
    for home in range(max_goals + 1):
        for away in range(max_goals + 1):
            series = 0.0
            for shared_goals in range(min(home, away) + 1):
                series += (
                    home_independent ** (home - shared_goals)
                    * away_independent ** (away - shared_goals)
                    * shared**shared_goals
                    / (
                        math.factorial(home - shared_goals)
                        * math.factorial(away - shared_goals)
                        * math.factorial(shared_goals)
                    )
                )
            matrix[(home, away)] = common * series
    mass = sum(matrix.values())
    return {score: value / mass for score, value in matrix.items()}


def probability_from_score_matrix(
    matrix: Mapping[tuple[int, int], float],
    market: Any,
) -> float | None:
    key = normalize_market(market)
    if key not in {
        "HOME_WIN", "DRAW", "AWAY_WIN", "DOUBLE_1X", "DOUBLE_X2", "DOUBLE_12",
        "BTTS_YES", "BTTS_NO", "OVER_0_5", "UNDER_0_5", "OVER_1_5",
        "UNDER_1_5", "OVER_2_5", "UNDER_2_5", "OVER_3_5", "UNDER_3_5",
        "OVER_4_5", "UNDER_4_5",
    }:
        return None
    result = 0.0
    for (home, away), cell in matrix.items():
        total = home + away
        accepted = {
            "HOME_WIN": home > away,
            "DRAW": home == away,
            "AWAY_WIN": home < away,
            "DOUBLE_1X": home >= away,
            "DOUBLE_X2": home <= away,
            "DOUBLE_12": home != away,
            "BTTS_YES": home > 0 and away > 0,
            "BTTS_NO": home == 0 or away == 0,
            "OVER_0_5": total > 0.5,
            "UNDER_0_5": total < 0.5,
            "OVER_1_5": total > 1.5,
            "UNDER_1_5": total < 1.5,
            "OVER_2_5": total > 2.5,
            "UNDER_2_5": total < 2.5,
            "OVER_3_5": total > 3.5,
            "UNDER_3_5": total < 3.5,
            "OVER_4_5": total > 4.5,
            "UNDER_4_5": total < 4.5,
        }[key]
        if accepted:
            result += cell
    return max(1e-6, min(1.0 - 1e-6, result))


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return dict(payload) if isinstance(payload, Mapping) else {}
    except Exception:
        return {}


class CatBoostShadowAdapter:
    """Optional CatBoost candidate; absence never blocks the production bot."""

    NUMERIC_FEATURES = (
        "home_xg",
        "away_xg",
        "home_rest_days",
        "away_rest_days",
        "home_form_home",
        "away_form_away",
        "feature_completeness",
    )
    CATEGORICAL_FEATURES = (
        "market",
        "league",
        "lineup_available",
        "injuries_available",
        "coach_change",
    )

    def __init__(self, state: Mapping[str, Any], state_dir: Path):
        self.status = "WAITING_FOR_VALIDATED_ARTIFACT"
        self.model = None
        self.metadata = dict(state.get("catboost", {})) if isinstance(
            state.get("catboost"), Mapping
        ) else {}
        raw_path = str(self.metadata.get("artifact_path", "")).strip()
        if not raw_path or self.metadata.get("validation_status") not in {
            "SHADOW_VALIDATED", "SHADOW_CANDIDATE"
        }:
            return
        artifact = Path(raw_path)
        if not artifact.is_absolute():
            artifact = state_dir / artifact
        if not artifact.exists():
            self.status = "ARTIFACT_MISSING"
            return
        try:
            from catboost import CatBoostClassifier

            self.model = CatBoostClassifier()
            self.model.load_model(str(artifact))
            self.status = "SHADOW_READY"
        except Exception as exc:
            self.status = f"DEPENDENCY_OR_ARTIFACT_ERROR:{type(exc).__name__}"

    @staticmethod
    def _feature_value(features: Mapping[str, Any], name: str) -> Any:
        value = features.get(name)
        if name in CatBoostShadowAdapter.CATEGORICAL_FEATURES:
            return str(value or "UNKNOWN")
        number = _number(value)
        return float("nan") if number is None else number

    def predict(self, features: Mapping[str, Any]) -> float | None:
        if self.model is None:
            return None
        ordered = self.NUMERIC_FEATURES + self.CATEGORICAL_FEATURES
        try:
            result = float(
                self.model.predict_proba(
                    [[self._feature_value(features, name) for name in ordered]]
                )[0][1]
            )
            return max(1e-6, min(1.0 - 1e-6, result))
        except Exception:
            self.status = "PREDICTION_ERROR"
            return None


@dataclass(frozen=True)
class FootballCouncilResult:
    version: str
    mode: str
    champion_remains_active: bool
    challengers_have_decision_authority: bool
    market: str
    models: dict[str, dict[str, Any]]
    diagnostic_consensus: float
    model_disagreement: float
    available_models: int
    gate_status: str
    bookmaker_used_as_model_input: bool

    def payload(self) -> dict[str, Any]:
        return asdict(self)


class FootballModelCouncil:
    """Evaluate heterogeneous football models without changing the Champion."""

    def __init__(self, state_path: str | Path | None = None):
        default = Path(get_data_dir()) / "football_model_council" / "shadow_state.json"
        self.state_path = Path(
            state_path or os.getenv("BETBOT_FOOTBALL_COUNCIL_STATE", default)
        )
        self.state = _read_json(self.state_path)
        self.catboost = CatBoostShadowAdapter(self.state, self.state_path.parent)
        self._poisson_cache: dict[
            tuple[float, float], dict[tuple[int, int], float]
        ] = {}
        self._bivariate_cache: dict[
            tuple[float, float, float], dict[tuple[int, int], float]
        ] = {}
        self._dixon_cache: dict[
            tuple[float, float, float], dict[str, float]
        ] = {}

    def _hierarchical_rates(
        self,
        home_xg: float,
        away_xg: float,
        league: str,
        home_team: str,
        away_team: str,
    ) -> tuple[float, float, str]:
        global_prior = self.state.get("global_prior", {})
        global_home = _number(
            global_prior.get("home_rate") if isinstance(global_prior, Mapping) else None
        ) or 1.45
        global_away = _number(
            global_prior.get("away_rate") if isinstance(global_prior, Mapping) else None
        ) or 1.15
        leagues = self.state.get("league_priors", {})
        league_prior = leagues.get(league, {}) if isinstance(leagues, Mapping) else {}
        prior_home = _number(
            league_prior.get("home_rate") if isinstance(league_prior, Mapping) else None
        ) or global_home
        prior_away = _number(
            league_prior.get("away_rate") if isinstance(league_prior, Mapping) else None
        ) or global_away
        teams = self.state.get("team_priors", {})
        home_prior = teams.get(home_team, {}) if isinstance(teams, Mapping) else {}
        away_prior = teams.get(away_team, {}) if isinstance(teams, Mapping) else {}
        if isinstance(home_prior, Mapping):
            prior_home = _number(home_prior.get("home_rate")) or prior_home
            home_samples = int(_number(home_prior.get("home_samples")) or 0)
        else:
            home_samples = 0
        if isinstance(away_prior, Mapping):
            prior_away = _number(away_prior.get("away_rate")) or prior_away
            away_samples = int(_number(away_prior.get("away_samples")) or 0)
        else:
            away_samples = 0
        # Sparse teams receive more shrinkage; established teams remain close
        # to their point-in-time xG estimate.
        prior_strength = max(
            1.0, _number(self.state.get("hierarchical_prior_strength")) or 6.0
        )
        home_evidence = max(2.0, min(20.0, float(home_samples or 8)))
        away_evidence = max(2.0, min(20.0, float(away_samples or 8)))
        home_rate = (
            home_xg * home_evidence + prior_home * prior_strength
        ) / (home_evidence + prior_strength)
        away_rate = (
            away_xg * away_evidence + prior_away * prior_strength
        ) / (away_evidence + prior_strength)
        source = "learned_hierarchy" if self.state else "conservative_default_hierarchy"
        return home_rate, away_rate, source

    @staticmethod
    def _entry(
        probability: float | None,
        *,
        status: str,
        method: str,
        details: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "probability": round(probability, 8) if probability is not None else None,
            "fair_odds": round(1.0 / probability, 6) if probability else None,
            "status": status,
            "method": method,
            "details": dict(details or {}),
        }

    def evaluate(
        self,
        *,
        champion_probability: Any,
        market: Any,
        home_xg: Any,
        away_xg: Any,
        features: Mapping[str, Any] | None = None,
    ) -> FootballCouncilResult:
        selected_market = normalize_market(market)
        champion = _probability(champion_probability)
        home = _number(home_xg)
        away = _number(away_xg)
        context = dict(features or {})
        context.update({
            "market": selected_market,
            "home_xg": home,
            "away_xg": away,
        })
        models: dict[str, dict[str, Any]] = {
            "champion": self._entry(
                champion,
                status="ACTIVE_CHAMPION" if champion is not None else "MISSING",
                method="verified_current_model",
            )
        }
        if home is None or away is None or home < 0 or away < 0:
            for name in MODEL_ORDER[1:]:
                models[name] = self._entry(
                    None, status="ABSTAIN_MISSING_XG", method=name
                )
        else:
            rate_key = (round(home, 8), round(away, 8))
            if rate_key not in self._poisson_cache:
                self._poisson_cache[rate_key] = poisson_score_matrix(home, away)
            poisson = probability_from_score_matrix(
                self._poisson_cache[rate_key], selected_market
            )
            models["poisson"] = self._entry(
                poisson, status="SHADOW_READY", method="independent_poisson"
            )
            rho = _number(context.get("dixon_coles_rho"))
            selected_rho = -0.08 if rho is None else rho
            dixon_key = (*rate_key, round(selected_rho, 8))
            if dixon_key not in self._dixon_cache:
                self._dixon_cache[dixon_key] = DixonColesEngine(
                    rho=selected_rho, max_goals=12
                ).market_probabilities(home, away)
            dixon_alias = {
                "DOUBLE_1X": "HOME_OR_DRAW",
                "DOUBLE_X2": "AWAY_OR_DRAW",
                "DOUBLE_12": "HOME_OR_AWAY",
            }.get(selected_market, selected_market)
            dixon = self._dixon_cache[dixon_key].get(dixon_alias)
            models["dixon_coles"] = self._entry(
                dixon,
                status="SHADOW_READY" if dixon is not None else "UNSUPPORTED_MARKET",
                method="dixon_coles_low_score_correction",
                details={"rho": selected_rho},
            )
            configured_shared = _number(self.state.get("bivariate_shared_rate"))
            shared = configured_shared
            if shared is None:
                shared = min(home, away) * 0.08
            bivariate_key = (*rate_key, round(shared, 8))
            if bivariate_key not in self._bivariate_cache:
                self._bivariate_cache[bivariate_key] = (
                    bivariate_poisson_score_matrix(
                        home, away, shared_rate=shared
                    )
                )
            bivariate = probability_from_score_matrix(
                self._bivariate_cache[bivariate_key], selected_market
            )
            models["bivariate_poisson"] = self._entry(
                bivariate,
                status="SHADOW_READY" if bivariate is not None else "UNSUPPORTED_MARKET",
                method="bivariate_poisson_shared_component",
                details={"shared_rate": round(shared, 6)},
            )
            hierarchical_home, hierarchical_away, hierarchy_source = (
                self._hierarchical_rates(
                    home,
                    away,
                    str(context.get("league") or "UNKNOWN"),
                    str(context.get("home_team") or "UNKNOWN"),
                    str(context.get("away_team") or "UNKNOWN"),
                )
            )
            hierarchical = probability_from_score_matrix(
                poisson_score_matrix(hierarchical_home, hierarchical_away),
                selected_market,
            )
            models["hierarchical_bayes"] = self._entry(
                hierarchical,
                status="SHADOW_READY",
                method="empirical_bayes_partial_pooling",
                details={
                    "home_rate": round(hierarchical_home, 6),
                    "away_rate": round(hierarchical_away, 6),
                    "prior_source": hierarchy_source,
                },
            )
            catboost = self.catboost.predict(context)
            models["catboost"] = self._entry(
                catboost,
                status=self.catboost.status,
                method="catboost_point_in_time_features",
                details={
                    "artifact_validation": self.catboost.metadata.get(
                        "validation_status", "NONE"
                    )
                },
            )
        available = {
            name: item["probability"]
            for name, item in models.items()
            if item.get("probability") is not None
        }
        configured = self.state.get("diagnostic_weights", {})
        configured = configured if isinstance(configured, Mapping) else {}
        weights = {}
        for name in available:
            configured_value = _number(configured.get(name))
            weights[name] = max(
                0.0,
                DEFAULT_WEIGHTS.get(name, 0.0)
                if configured_value is None
                else configured_value,
            )
        total_weight = sum(weights.values()) or 1.0
        consensus = sum(
            probability * weights[name] for name, probability in available.items()
        ) / total_weight
        disagreement = (
            pstdev(available.values()) if len(available) > 1 else 0.0
        )
        minimum_models = max(
            3, int(_number(os.getenv("BETBOT_FOOTBALL_COUNCIL_MIN_MODELS")) or 4)
        )
        maximum_disagreement = max(
            0.01,
            _number(os.getenv("BETBOT_FOOTBALL_COUNCIL_MAX_DISAGREEMENT")) or 0.12,
        )
        if len(available) < minimum_models:
            gate = "WAITING_FOR_MODELS"
        elif disagreement > maximum_disagreement:
            gate = "SHADOW_REVIEW_HIGH_DISAGREEMENT"
        else:
            gate = "SHADOW_CONSENSUS"
        return FootballCouncilResult(
            version=COUNCIL_VERSION,
            mode="SHADOW_ONLY",
            champion_remains_active=True,
            challengers_have_decision_authority=False,
            market=selected_market,
            models=models,
            diagnostic_consensus=round(consensus, 8),
            model_disagreement=round(disagreement, 8),
            available_models=len(available),
            gate_status=gate,
            bookmaker_used_as_model_input=False,
        )
