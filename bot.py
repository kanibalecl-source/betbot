import json
import hashlib
import pandas as pd
from datetime import datetime
from pathlib import Path

from data_api import get_matches, get_odds_market_data
from model_goals import build_model
from team_stats import get_match_xg

# =========================
# OPTIONAL STAGE IMPORTS
# =========================

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
    from market_movement_engine import MarketMovementEngine
except Exception:
    MarketMovementEngine = None

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
    from clv_engine import CLVEngine
except Exception:
    CLVEngine = None


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

ALL_FILE = DATA_DIR / "auto_all_picks.csv"
HISTORY_FILE = DATA_DIR / "auto_all_picks_history.csv"
CLV_FILE = DATA_DIR / "clv_history.csv"
CONFIG_FILE = BASE_DIR / "config_strategy.json"


# =========================
# CONFIG
# =========================

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# =========================
# BASIC HELPERS
# =========================

def format_bet(market):
    mapping = {
        "HOME_WIN": "Home Win",
        "DRAW": "Draw",
        "AWAY_WIN": "Away Win",
        "BTTS_YES": "BTTS Yes",
        "BTTS_NO": "BTTS No",
        "OVER_2.5": "Over 2.5",
        "UNDER_2.5": "Under 2.5",
        "OVER_1.5": "Over 1.5",
        "UNDER_1.5": "Under 1.5"
    }
    return mapping.get(market, market)


def market_to_odds_api(market):
    if market in {"HOME_WIN", "DRAW", "AWAY_WIN"}:
        return "h2h"
    if market in {"OVER_2.5", "UNDER_2.5", "OVER_1.5", "UNDER_1.5"}:
        return "totals"
    if market in {"BTTS_YES", "BTTS_NO"}:
        return "btts"
    return "h2h"


def outcome_name_for_closing(match, market):
    if market == "HOME_WIN":
        return match.get("home_team") or match.get("home")
    if market == "AWAY_WIN":
        return match.get("away_team") or match.get("away")
    if market == "DRAW":
        return "Draw"
    if market in {"OVER_2.5", "OVER_1.5"}:
        return "Over"
    if market in {"UNDER_2.5", "UNDER_1.5"}:
        return "Under"
    if market == "BTTS_YES":
        return "Yes"
    if market == "BTTS_NO":
        return "No"
    return None


def get_market_group(market):
    groups = {
        "HOME_WIN": ["HOME_WIN", "DRAW", "AWAY_WIN"],
        "DRAW": ["HOME_WIN", "DRAW", "AWAY_WIN"],
        "AWAY_WIN": ["HOME_WIN", "DRAW", "AWAY_WIN"],
        "BTTS_YES": ["BTTS_YES", "BTTS_NO"],
        "BTTS_NO": ["BTTS_YES", "BTTS_NO"],
        "OVER_2.5": ["OVER_2.5", "UNDER_2.5"],
        "UNDER_2.5": ["OVER_2.5", "UNDER_2.5"],
        "OVER_1.5": ["OVER_1.5", "UNDER_1.5"],
        "UNDER_1.5": ["OVER_1.5", "UNDER_1.5"],
    }
    return groups.get(market)


def calculate_market_margin(odds_dict, market):
    group = get_market_group(market)
    if not group:
        return None

    probs = []

    for outcome in group:
        data = odds_dict.get(outcome)
        if not data:
            continue

        odd = data.get("best_odds")

        if odd and odd > 1:
            probs.append(1 / odd)

    if len(probs) != len(group):
        return None

    return sum(probs)


def remove_margin(book_prob, margin_sum):
    if not margin_sum or margin_sum <= 0:
        return book_prob
    return book_prob / margin_sum


def blend_probability(model_prob, true_book_prob, model_weight, market_weight):
    blended = (model_weight * model_prob) + (market_weight * true_book_prob)
    return min(max(blended, 0.01), 0.99)


def kelly_fraction(prob, odds):
    b = odds - 1
    q = 1 - prob

    if b <= 0:
        return 0.0

    return max(((b * prob) - q) / b, 0.0)


def classify_risk(final_prob, edge, ev, margin_sum, thresholds):
    for label in ["top", "low", "risk"]:
        t = thresholds[label]

        if (
            edge >= t["min_edge"]
            and ev >= t["min_ev"]
            and final_prob >= t["min_probability"]
            and margin_sum <= t["max_margin_sum"]
        ):
            return label.upper()

    return "SKIP"


def make_pick_id(match, market, book_odds):
    raw = "|".join([
        str(match.get("fixture_id", "")),
        str(match.get("match", "")),
        str(match.get("match_date", "")),
        str(market),
        str(book_odds),
    ])

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def safe_match_value(match, *keys, default=""):
    for key in keys:
        value = match.get(key)

        if value not in [None, ""]:
            return value

    return default


def preserve_existing_file_when_empty():
    if ALL_FILE.exists():
        print("⚠️ Brak nowych typów — zachowuję poprzedni auto_all_picks.csv")
        return

    pd.DataFrame([]).to_csv(ALL_FILE, index=False)
    print("⚠️ Brak typów i brak starego pliku — utworzono pusty CSV")


def clamp_probability(value):
    try:
        value = float(value)
        if value > 1:
            value = value / 100
        return min(max(value, 0.01), 0.99)
    except Exception:
        return 0.50


def safe_float(value, default=0.0):
    try:
        if value in [None, ""]:
            return default
        return float(value)
    except Exception:
        return default


# =========================
# STAGE ENGINE HELPERS
# =========================

def build_stage_engines():
    return {
        "tempo": TempoEngine() if TempoEngine else None,
        "confidence": ConfidenceCalibration() if ConfidenceCalibration else None,
        "xg": XGEngine() if XGEngine else None,
        "value": MarketValueEngine() if MarketValueEngine else None,
        "movement": MarketMovementEngine() if MarketMovementEngine else None,
        "bayesian": BayesianLiveEngine() if BayesianLiveEngine else None,
        "ensemble": EnsembleEngine() if EnsembleEngine else None,
        "filter": FilterOptimizer() if FilterOptimizer else None,
        "bankroll": BankrollEngine() if BankrollEngine else None,
        "risk": RiskManager() if RiskManager else None,
        "clv": CLVEngine() if CLVEngine else None,
    }


def stage_tempo(engines, match, home_xg, away_xg):
    pressure = safe_float(match.get("pressure"), 50)
    momentum = safe_float(match.get("momentum"), 50)
    shots_on_target = safe_float(match.get("shots_on_target"), 0)
    dangerous_attacks = safe_float(match.get("dangerous_attacks"), 0)
    possession = safe_float(match.get("possession"), 50)
    xg_live = safe_float(match.get("xg_live"), (home_xg + away_xg) / 2)

    if engines["tempo"]:
        tempo = engines["tempo"].calculate_tempo(
            shots_on_target=shots_on_target,
            dangerous_attacks=dangerous_attacks,
            possession=possession,
            pressure=pressure,
            xg_live=xg_live
        )
    else:
        score = (pressure + momentum) / 2
        level = "HIGH" if score >= 75 else "MEDIUM" if score >= 45 else "LOW"
        tempo = {
            "tempo_score": round(score, 2),
            "tempo_level": level
        }

    return tempo, pressure, momentum


def stage_probability(
    engines,
    market,
    model_prob,
    true_book_prob,
    book_odds,
    home_xg,
    away_xg,
    tempo_score,
    pressure,
    momentum,
    model_weight,
    market_weight
):
    # Existing stable probability
    blended_prob = blend_probability(
        model_prob,
        true_book_prob,
        model_weight,
        market_weight
    )

    # ETAP 3 — xG helper probability
    xg_probability = None
    if engines["xg"]:
        try:
            xg_probability = engines["xg"].calculate_probability(home_xg, away_xg)
        except Exception:
            xg_probability = None

    # ETAP 5 — Bayesian LIVE adjustment
    bayesian_probability = blended_prob
    if engines["bayesian"]:
        try:
            bayesian_probability = engines["bayesian"].update_probability(
                prematch_probability=blended_prob,
                tempo_score=tempo_score,
                pressure=pressure,
                momentum=momentum
            )
        except Exception:
            bayesian_probability = blended_prob

    # ETAP 6 — Ensemble
    ensemble_probability = bayesian_probability
    if engines["ensemble"]:
        try:
            ensemble_probability = engines["ensemble"].combine_probabilities(
                xg_probability=xg_probability,
                market_probability=true_book_prob,
                ml_probability=bayesian_probability
            )
        except Exception:
            ensemble_probability = bayesian_probability

    # ETAP 2 — calibration
    calibrated_probability = ensemble_probability
    if engines["confidence"]:
        try:
            calibrated_probability = engines["confidence"].calibrate(ensemble_probability)
        except Exception:
            calibrated_probability = ensemble_probability

    final_probability = clamp_probability(calibrated_probability)

    # Bookmaker odds protection: avoid irrational drift from calibration
    # Final probability is blended 70% old stable model, 30% stage engine.
    final_probability = clamp_probability((blended_prob * 0.70) + (final_probability * 0.30))

    fair_odds_model = 1 / clamp_probability(model_prob)
    fair_odds_final = 1 / final_probability

    return {
        "blended_prob": blended_prob,
        "xg_probability": xg_probability,
        "bayesian_probability": bayesian_probability,
        "ensemble_probability": ensemble_probability,
        "final_probability": final_probability,
        "fair_odds_model": fair_odds_model,
        "fair_odds_final": fair_odds_final
    }


def stage_ev(engines, final_probability, book_odds):
    if engines["value"]:
        try:
            # market_value_engine returns percent value
            ev_percent = engines["value"].calculate_ev(final_probability, book_odds)
            return ev_percent / 100
        except Exception:
            pass

    return (book_odds * final_probability) - 1


def stage_movement(engines, book_odds, opening_odds=None):
    opening_odds = safe_float(opening_odds, book_odds)

    if engines["movement"]:
        try:
            return engines["movement"].calculate_movement(
                opening_odds=opening_odds,
                current_odds=book_odds
            )
        except Exception:
            pass

    return {
        "movement_percent": 0,
        "direction": "STABLE",
        "signal": "NO_SIGNAL"
    }


def stage_filter(engines, confidence_percent, ev_percent, tempo_level):
    if engines["filter"]:
        try:
            # UWAGA: nie blokujemy agresywnie, żeby nie wyzerować bota.
            return engines["filter"].should_accept_pick(
                confidence=confidence_percent,
                ev=ev_percent,
                min_confidence=1,
                min_ev=-100,
                league_allowed=True,
                market_allowed=True,
                tempo_level=None
            )
        except Exception:
            pass

    return {
        "accepted": True,
        "reason": "ACCEPTED"
    }


def stage_bankroll(engines, bankroll, probability, odds):
    if engines["bankroll"]:
        try:
            stake = engines["bankroll"].recommended_stake(
                bankroll=bankroll,
                probability=probability,
                odds=odds,
                fraction=0.25,
                max_percent=2
            )
            fraction = engines["bankroll"].kelly_fraction(probability, odds)
            return stake, fraction
        except Exception:
            pass

    fraction = kelly_fraction(probability, odds)
    return round(bankroll * fraction * 0.25, 2), fraction


def stage_risk(engines, confidence_percent, ev_percent, tempo_level, fallback_risk):
    if engines["risk"]:
        try:
            return engines["risk"].risk_label(
                confidence=confidence_percent,
                ev=ev_percent,
                tempo_level=tempo_level
            )
        except Exception:
            pass

    return fallback_risk


def stage_clv(engines, book_odds, closing_odds=None):
    if closing_odds in [None, ""]:
        return 0, "PENDING_CLV"

    if engines["clv"]:
        try:
            clv = engines["clv"].calculate_clv(book_odds, closing_odds)
            return clv, engines["clv"].clv_status(clv)
        except Exception:
            pass

    return 0, "PENDING_CLV"


# =========================
# MAIN BOT
# =========================

def run_bot():
    print("=== BOT START: CORE + STAGES 1-10 INTEGRATED ===")

    cfg = load_config()
    filters = cfg["filters"]
    model_weight = cfg["model"]["model_weight"]
    market_weight = cfg["model"]["market_weight"]
    active_markets = cfg["active_markets"]
    thresholds = cfg["risk_thresholds"]
    bankroll_size = safe_float(cfg.get("bankroll", 1000), 1000)

    engines = build_stage_engines()

    print("✅ STAGE ENGINES:")
    for name, engine in engines.items():
        print(f" - {name}: {'ON' if engine else 'OFF'}")

    matches = get_matches()

    print(f"✅ MECZE: {len(matches)}")
    print("🔎 SAMPLE:", matches[:3])

    rows = []
    skip_stats = {
        "no_odds": 0,
        "no_xg": 0,
        "inactive_market": 0,
        "no_model_prob": 0,
        "odds_range": 0,
        "margin": 0,
        "edge_ev": 0,
        "risk_skip": 0,
        "stage_filter_rejected": 0,
    }

    if not matches:
        print("⚠️ BRAK MECZÓW Z API — nie nadpisuję starego CSV")
        preserve_existing_file_when_empty()
        print(f"📈 SKIP STATS: {skip_stats}")
        print("✅ GOTOWE")
        print("📊 0 nowych typów zapisanych")
        print(f"📁 {ALL_FILE}")
        return

    for match in matches:
        odds_data = get_odds_market_data(match)

        if not odds_data:
            skip_stats["no_odds"] += 1
            continue

        home_xg, away_xg = get_match_xg(match)

        if home_xg is None or away_xg is None:
            skip_stats["no_xg"] += 1
            continue

        model = build_model(home_xg, away_xg)

        fixture_id = safe_match_value(match, "fixture_id", "id")
        odds_event_id = safe_match_value(match, "odds_event_id", "event_id")
        home_team = safe_match_value(match, "home_team", "home")
        away_team = safe_match_value(match, "away_team", "away")
        match_date = safe_match_value(match, "match_date", "date", "commence_time")
        minute = safe_match_value(match, "minute", "min", "elapsed", default="")
        score = safe_match_value(match, "score", "wynik", default="")
        match_status = safe_match_value(match, "status", default="NEW")

        tempo_data, pressure, momentum = stage_tempo(
            engines,
            match,
            home_xg,
            away_xg
        )

        tempo_score = tempo_data.get("tempo_score", 0)
        tempo_level = tempo_data.get("tempo_level", "LOW")

        for market, data in odds_data.items():
            if not active_markets.get(market, True):
                skip_stats["inactive_market"] += 1
                continue

            model_prob = model.get(market)

            if not model_prob or model_prob <= 0:
                skip_stats["no_model_prob"] += 1
                continue

            book_odds = data.get("best_odds")
            bookmaker = data.get("bookmaker", data.get("site", ""))

            if not book_odds or book_odds < filters["min_book_odds"] or book_odds > filters["max_book_odds"]:
                skip_stats["odds_range"] += 1
                continue

            margin_sum = calculate_market_margin(odds_data, market)

            if not margin_sum or margin_sum > filters["max_margin_sum"]:
                skip_stats["margin"] += 1
                continue

            book_prob = 1 / book_odds
            true_book_prob = remove_margin(book_prob, margin_sum)

            model_prob = clamp_probability(model_prob)
            true_book_prob = clamp_probability(true_book_prob)

            probability_data = stage_probability(
                engines=engines,
                market=market,
                model_prob=model_prob,
                true_book_prob=true_book_prob,
                book_odds=book_odds,
                home_xg=home_xg,
                away_xg=away_xg,
                tempo_score=tempo_score,
                pressure=pressure,
                momentum=momentum,
                model_weight=model_weight,
                market_weight=market_weight
            )

            final_prob = probability_data["final_probability"]
            fair_odds_model = probability_data["fair_odds_model"]
            fair_odds_final = probability_data["fair_odds_final"]

            edge = (final_prob / true_book_prob) - 1
            ev = stage_ev(engines, final_prob, book_odds)

            if edge < filters["min_edge"] or ev < filters["min_ev"] or edge > filters["max_edge"]:
                skip_stats["edge_ev"] += 1
                continue

            risk_level = classify_risk(
                final_prob,
                edge,
                ev,
                margin_sum,
                thresholds
            )

            if risk_level == "SKIP":
                skip_stats["risk_skip"] += 1
                continue

            confidence_percent = round(final_prob * 100, 2)
            ev_percent = round(ev * 100, 2)

            filter_decision = stage_filter(
                engines,
                confidence_percent,
                ev_percent,
                tempo_level
            )

            if not filter_decision.get("accepted", True):
                skip_stats["stage_filter_rejected"] += 1
                continue

            ai_risk = stage_risk(
                engines,
                confidence_percent,
                ev_percent,
                tempo_level,
                risk_level
            )

            full_kelly = kelly_fraction(final_prob, book_odds)
            quarter_kelly = min(full_kelly * 0.25, 0.05)

            recommended_stake, stage_kelly_fraction = stage_bankroll(
                engines,
                bankroll_size,
                final_prob,
                book_odds
            )

            movement = stage_movement(
                engines,
                book_odds,
                data.get("opening_odds")
            )

            closing_odds = data.get("closing_odds")
            clv_percent, clv_status = stage_clv(
                engines,
                book_odds,
                closing_odds
            )

            league_full = f"{match['league']} / {match.get('country', '')}"
            pick_id = make_pick_id(match, market, book_odds)

            rows.append({
                "pick_id": pick_id,
                "fixture_id": fixture_id,
                "odds_event_id": odds_event_id,
                "home_team": home_team,
                "away_team": away_team,
                "home": home_team,
                "away": away_team,
                "match_date": match_date,
                "minute": minute,
                "score": score,

                "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "liga": league_full,
                "league": match.get("league", ""),
                "country": match.get("country", ""),
                "mecz": match["match"],
                "match": match["match"],
                "market": market,
                "signal": format_bet(market),
                "typ": format_bet(market),
                "bookmaker": bookmaker,

                "odds_api_market": market_to_odds_api(market),
                "closing_outcome_name": outcome_name_for_closing(match, market),

                "kurs_buk": round(book_odds, 2),
                "odds": round(book_odds, 2),
                "kurs_model": round(fair_odds_model, 2),
                "kurs_bota": round(fair_odds_final, 2),
                "fair_odds": round(fair_odds_final, 2),

                "prawd_model": round(model_prob, 4),
                "prawd_rynek": round(true_book_prob, 4),
                "prawd_final": round(final_prob, 4),
                "confidence": confidence_percent,

                "xg_probability": probability_data["xg_probability"],
                "bayesian_probability": probability_data["bayesian_probability"],
                "ensemble_probability": probability_data["ensemble_probability"],

                "edge": round(edge, 4),
                "ev": round(ev, 4),
                "ev_percent": ev_percent,

                "kelly_full": round(full_kelly, 4),
                "kelly_25": round(quarter_kelly, 4),
                "stage_kelly_fraction": round(stage_kelly_fraction, 4),
                "recommended_stake": recommended_stake,
                "stake": recommended_stake,

                "home_xg": round(home_xg, 3),
                "away_xg": round(away_xg, 3),

                "tempo_score": tempo_score,
                "tempo_level": tempo_level,
                "pressure": pressure,
                "momentum": momentum,

                "market_movement": movement.get("movement_percent", 0),
                "market_direction": movement.get("direction", "STABLE"),
                "market_signal": movement.get("signal", "NO_SIGNAL"),

                "clv_percent": clv_percent,
                "clv_status": clv_status,

                "filter_status": "ACCEPTED",
                "filter_reason": filter_decision.get("reason", "ACCEPTED"),

                "marza_sum": round(margin_sum, 4),
                "marza_%": round((margin_sum - 1) * 100, 2),
                "risk_level": risk_level,
                "ai_risk": ai_risk,
                "risk": ai_risk,
                "status": match_status if match_status else "NEW"
            })

    df = pd.DataFrame(rows)

    if not df.empty:
        risk_order = {"TOP": 0, "LOW": 1, "RISK": 2, "MEDIUM": 3, "HIGH": 4}
        df["_risk_sort"] = df["risk_level"].map(risk_order).fillna(9)
        df = df.sort_values(
            by=["_risk_sort", "ev", "edge"],
            ascending=[True, False, False]
        )
        df = df.drop(columns=["_risk_sort"])

        df.to_csv(ALL_FILE, index=False)

        if HISTORY_FILE.exists():
            df.to_csv(HISTORY_FILE, mode="a", index=False, header=False)
        else:
            df.to_csv(HISTORY_FILE, index=False)

    else:
        preserve_existing_file_when_empty()

    print(f"📈 SKIP STATS: {skip_stats}")
    print("✅ GOTOWE")
    print(f"📊 {len(df)} typów zapisanych")
    print(f"📁 {ALL_FILE}")
    print("✅ ETAPY AKTYWNE: tempo, confidence, xg, market movement, bayesian, ensemble, filter, bankroll, clv")


if __name__ == "__main__":
    run_bot()
