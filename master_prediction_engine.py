from datetime import datetime
from pathlib import Path
import math

# Optional imports. Engine works even if some etap files are missing.
try:
    from tempo_engine import TempoEngine
except Exception:
    TempoEngine = None

try:
    from confidence_engine import ConfidenceCalibration
except Exception:
    ConfidenceCalibration = None

try:
    from xg_engine import XGEngine
except Exception:
    XGEngine = None

try:
    from market_value_engine import MarketValueEngine
except Exception:
    MarketValueEngine = None

try:
    from bayesian_live_engine import BayesianLiveEngine
except Exception:
    BayesianLiveEngine = None

try:
    from ensemble_engine import EnsembleEngine
except Exception:
    EnsembleEngine = None

try:
    from filter_optimizer import FilterOptimizer
except Exception:
    FilterOptimizer = None

try:
    from bankroll_engine import BankrollEngine
except Exception:
    BankrollEngine = None

try:
    from risk_manager import RiskManager
except Exception:
    RiskManager = None

try:
    from market_movement_engine import MarketMovementEngine
except Exception:
    MarketMovementEngine = None


def _to_float(value, default=0.0):
    try:
        if value is None:
            return default
        value = str(value).replace("%", "").strip()
        if value == "" or value.lower() in ["nan", "none", "null"]:
            return default
        return float(value)
    except Exception:
        return default


def _first(source, keys, default=""):
    for key in keys:
        if key in source:
            value = source.get(key)
            if value is None:
                continue
            value = str(value).strip()
            if value and value.lower() not in ["nan", "none", "null"]:
                return value
    return default


class MasterPredictionEngine:
    """
    Centralny pipeline ETAPÓW 1–10.

    Wejście: dict z meczu / typu / rekordu API.
    Wyjście: dict gotowy do zapisu CSV i dashboardu.

    Ten silnik jest bezpieczny:
    - nie wywala bota, gdy brakuje danych,
    - używa fallbacków,
    - nie wymaga wszystkich etapów naraz.
    """

    def __init__(self, bankroll=1000):
        self.bankroll = bankroll

        self.tempo_engine = TempoEngine() if TempoEngine else None
        self.confidence_engine = ConfidenceCalibration() if ConfidenceCalibration else None
        self.xg_engine = XGEngine() if XGEngine else None
        self.value_engine = MarketValueEngine() if MarketValueEngine else None
        self.bayesian_engine = BayesianLiveEngine() if BayesianLiveEngine else None
        self.ensemble_engine = EnsembleEngine() if EnsembleEngine else None
        self.filter_optimizer = FilterOptimizer() if FilterOptimizer else None
        self.bankroll_engine = BankrollEngine() if BankrollEngine else None
        self.risk_manager = RiskManager() if RiskManager else None
        self.market_movement_engine = MarketMovementEngine() if MarketMovementEngine else None

    def process_match(self, match):
        try:
            home = _first(match, ["home", "home_team", "gospodarze"], "")
            away = _first(match, ["away", "away_team", "goscie"], "")
            league = _first(match, ["league", "liga"], "")
            minute = _first(match, ["minute", "min", "elapsed", "time"], "")
            score = _first(match, ["score", "wynik"], "")
            signal = _first(match, ["signal", "typ", "market", "pick"], "")
            market = _first(match, ["market", "signal", "typ"], signal)
            status = _first(match, ["status"], "LIVE")

            bookmaker_odds = _to_float(
                _first(match, ["odds", "kurs_buk", "bookmaker_odds", "current_odds"], "0"),
                0
            )

            # xG inputs
            home_xg = _to_float(_first(match, ["home_xg", "xg_home"], "0"), 0)
            away_xg = _to_float(_first(match, ["away_xg", "xg_away"], "0"), 0)

            # Base probability from existing fields or xG
            raw_probability = _to_float(
                _first(
                    match,
                    ["probability", "prawd_final", "prawd_model"],
                    "0"
                ),
                0
            )

            if raw_probability > 1:
                raw_probability = raw_probability / 100

            if raw_probability <= 0:
                return {
                    **dict(match), "probability": None, "fair_odds": None,
                    "confidence": 0, "ev": None, "filter_status": "REJECTED",
                    "filter_reason": "MISSING_VERIFIED_MARKET_PROBABILITY",
                    "probability_source": "NO_DATA",
                }

            # ETAP 2 — Tempo
            shots_on_target = _to_float(_first(match, ["shots_on_target", "sot"], "0"), 0)
            dangerous_attacks = _to_float(_first(match, ["dangerous_attacks"], "0"), 0)
            possession = _to_float(_first(match, ["possession"], "50"), 50)
            pressure = _to_float(_first(match, ["pressure"], "0"), 0)
            momentum = _to_float(_first(match, ["momentum"], "0"), 0)
            xg_live = _to_float(_first(match, ["xg_live"], "0"), 0)

            tempo_score = 0
            tempo_level = "LOW"

            if self.tempo_engine:
                tempo_data = self.tempo_engine.calculate_tempo(
                    shots_on_target=shots_on_target,
                    dangerous_attacks=dangerous_attacks,
                    possession=possession,
                    pressure=pressure,
                    xg_live=xg_live
                )
                tempo_score = tempo_data.get("tempo_score", 0)
                tempo_level = tempo_data.get("tempo_level", "LOW")
            else:
                tempo_score = (pressure + momentum) / 2 if (pressure or momentum) else 0
                tempo_level = "HIGH" if tempo_score >= 75 else "MEDIUM" if tempo_score >= 45 else "LOW"

            # ETAP 5 — Bayesian LIVE
            live_probability = raw_probability
            if self.bayesian_engine:
                live_probability = self.bayesian_engine.update_probability(
                    prematch_probability=raw_probability,
                    tempo_score=tempo_score,
                    pressure=pressure,
                    momentum=momentum,
                    red_card_for=bool(match.get("red_card_for", False)),
                    red_card_against=bool(match.get("red_card_against", False)),
                    score_state=_to_float(_first(match, ["score_state"], "0"), 0)
                )

            # ETAP 6 — Ensemble
            ensemble_probability = live_probability
            if self.ensemble_engine:
                market_probability = 1 / bookmaker_odds if bookmaker_odds > 1 else None
                ensemble_probability = self.ensemble_engine.combine_probabilities(
                    xg_probability=raw_probability,
                    market_probability=market_probability,
                    ml_probability=live_probability
                )

            # ETAP 2 — Confidence calibration
            calibrated_probability = ensemble_probability
            if self.confidence_engine:
                calibrated_probability = self.confidence_engine.calibrate(ensemble_probability)

            # Own odds cannot use bookmaker prices or untrained fixed
            # calibration. Preserve the verified market-model input exactly.
            if raw_probability >= 1:
                return {
                    **dict(match), "probability": None, "fair_odds": None,
                    "confidence": 0, "ev": None, "filter_status": "REJECTED",
                    "filter_reason": "INVALID_MARKET_PROBABILITY",
                    "probability_source": "INVALID_DATA",
                }
            final_probability = float(raw_probability)
            confidence_percent = round(final_probability * 100, 2)

            # Fair odds + EV
            fair_odds = round(1 / final_probability, 2) if final_probability > 0 else 999

            ev = _to_float(_first(match, ["ev", "EV"], "0"), 0)
            if self.value_engine and bookmaker_odds > 1:
                ev = self.value_engine.calculate_ev(final_probability, bookmaker_odds)
            elif bookmaker_odds > 1:
                ev = round(((final_probability * bookmaker_odds) - 1) * 100, 2)

            # ETAP 4 — Market movement
            opening_odds = _to_float(_first(match, ["opening_odds"], "0"), 0)
            market_movement = 0
            market_direction = "UNKNOWN"
            market_signal = "NO_SIGNAL"

            if self.market_movement_engine and opening_odds > 1 and bookmaker_odds > 1:
                movement = self.market_movement_engine.calculate_movement(
                    opening_odds=opening_odds,
                    current_odds=bookmaker_odds
                )
                market_movement = movement.get("movement_percent", 0)
                market_direction = movement.get("direction", "UNKNOWN")
                market_signal = movement.get("signal", "NO_SIGNAL")

            # ETAP 9 — Risk + bankroll
            risk = "MEDIUM"
            if self.risk_manager:
                risk = self.risk_manager.risk_label(
                    confidence=confidence_percent,
                    ev=ev,
                    tempo_level=tempo_level
                )
            else:
                if confidence_percent >= 75 and ev >= 10:
                    risk = "LOW"
                elif confidence_percent >= 65 and ev >= 5:
                    risk = "MEDIUM"
                else:
                    risk = "HIGH"

            recommended_stake = _to_float(_first(match, ["stake", "recommended_stake"], "0"), 0)
            if self.bankroll_engine and bookmaker_odds > 1:
                recommended_stake = self.bankroll_engine.recommended_stake(
                    bankroll=self.bankroll,
                    probability=final_probability,
                    odds=bookmaker_odds,
                    fraction=0.25,
                    max_percent=2
                )

            # ETAP 8 — Filter optimizer
            filter_status = "ACCEPTED"
            filter_reason = "ACCEPTED"

            if self.filter_optimizer:
                decision = self.filter_optimizer.should_accept_pick(
                    confidence=confidence_percent,
                    ev=ev,
                    min_confidence=60,
                    min_ev=0,
                    league_allowed=True,
                    market_allowed=True,
                    tempo_level=tempo_level
                )
                filter_status = "ACCEPTED" if decision.get("accepted") else "REJECTED"
                filter_reason = decision.get("reason", "UNKNOWN")

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "home": home,
                "away": away,
                "league": league,
                "minute": minute,
                "score": score,
                "market": market,
                "signal": signal,
                "odds": bookmaker_odds,
                "fair_odds": fair_odds,
                "confidence": confidence_percent,
                "probability": round(final_probability, 4),
                "probability_source": "VERIFIED_INPUT_OR_MARKET_MODEL",
                "bookmaker_used_in_own_odds": False,
                "calibration_applied": False,
                "ev": ev,
                "tempo_score": tempo_score,
                "tempo_level": tempo_level,
                "pressure": pressure,
                "momentum": momentum,
                "status": status,
                "risk": risk,
                "stake": recommended_stake,
                "opening_odds": opening_odds,
                "market_movement": market_movement,
                "market_direction": market_direction,
                "market_signal": market_signal,
                "filter_status": filter_status,
                "filter_reason": filter_reason,
            }

        except Exception as e:
            print(f"❌ MASTER ENGINE ERROR: {e}")
            fallback = dict(match)
            fallback.setdefault("confidence", 0)
            fallback.setdefault("ev", 0)
            fallback.setdefault("filter_status", "ERROR")
            fallback.setdefault("filter_reason", str(e))
            return fallback
