from stage_a_value_layer import StageAValueLayer
import argparse
import math
import os
from stage_b_model_layer import StageBModelLayer
from stage_c_meta_layer import StageCMetaLayer
import json
import hashlib
import pandas as pd
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    from betbot.storage.append_only_history import append_event, append_records
except Exception:
    def append_event(*args, **kwargs):
        return None
    def append_records(*args, **kwargs):
        return 0

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
try:
    from storage_paths import DATA_DIR
except Exception:
    DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

ALL_FILE = DATA_DIR / "auto_all_picks.csv"
HISTORY_FILE = DATA_DIR / "auto_all_picks_history.csv"
CLV_FILE = DATA_DIR / "clv_history.csv"
CONFIG_FILE = BASE_DIR / "config_strategy.json"

BOT_MODE_SETTINGS = {
    "main": {"profile": None, "all_file": "auto_all_picks.csv", "history_file": "auto_all_picks_history.csv", "label": "PREMATCH"},
    "low": {"profile": "medium", "all_file": "auto_low_picks.csv", "history_file": "auto_low_picks_history.csv", "label": "PREMATCH LOW"},
    "risk": {"profile": "risk", "all_file": "auto_risk_picks.csv", "history_file": "auto_risk_picks_history.csv", "label": "PREMATCH RISK"},
}

TARGET_MARKETS = {
    "DOUBLE_1X",
    "DOUBLE_X2",
    "DOUBLE_12",

    "BTTS_YES",
    "BTTS_NO",

    "OVER_0.5",
    "OVER_1.5",
    "OVER_2.5",
    "OVER_3.5",
    "OVER_4.5",

    "UNDER_0.5",
    "UNDER_1.5",
    "UNDER_2.5",
    "UNDER_3.5",
    "UNDER_4.5",
}

# Overlapping double-chance outcomes are disabled until they are derived from
# a complete 1X2 market from the same bookmaker.
DISABLED_AUTOMATIC_MARKETS = {"DOUBLE_1X", "DOUBLE_X2", "DOUBLE_12"}


@dataclass(frozen=True)
class MarketMargin:
    bookmaker: str
    overround: float
    prices: dict[str, float]
    observed_at: str



# =========================
# CONFIG
# =========================

def load_config(profile_override=None):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    apply_active_filter_profile(cfg, profile_override=profile_override)
    return cfg


def apply_active_filter_profile(cfg, profile_override=None):
    profiles = cfg.get("filter_profiles", {}) or {}
    active = str(profile_override or cfg.get("active_filter_profile", "medium")).lower()
    profile = profiles.get(active) or profiles.get("medium") or {}
    filters = cfg.setdefault("filters", {})
    if "min_book_odds" in profile:
        filters["min_book_odds"] = safe_float(profile.get("min_book_odds"), filters.get("min_book_odds", 1.0))
    if "max_book_odds" in profile:
        filters["max_book_odds"] = safe_float(profile.get("max_book_odds"), filters.get("max_book_odds", 3.5))
    cfg["active_filter_profile"] = active if active in profiles else "medium"


# =========================
# BASIC HELPERS
# =========================

def format_bet(market):
    mapping = {
        "HOME_WIN": "1",
        "DRAW": "X",
        "AWAY_WIN": "2",

        "DOUBLE_1X": "1X",
        "DOUBLE_X2": "X2",
        "DOUBLE_12": "12",

        "BTTS_YES": "BTTS Yes",
        "BTTS_NO": "BTTS No",

        "OVER_0.5": "Over 0.5",
        "UNDER_0.5": "Under 0.5",

        "OVER_1.5": "Over 1.5",
        "UNDER_1.5": "Under 1.5",

        "OVER_2.5": "Over 2.5",
        "UNDER_2.5": "Under 2.5",

        "OVER_3.5": "Over 3.5",
        "UNDER_3.5": "Under 3.5",

        "OVER_4.5": "Over 4.5",
        "UNDER_4.5": "Under 4.5",
    }
    return mapping.get(market, market)


def market_to_odds_api(market):
    if market in {"HOME_WIN", "DRAW", "AWAY_WIN"}:
        return "h2h"

    if market in {"DOUBLE_1X", "DOUBLE_X2", "DOUBLE_12"}:
        return "double_chance"

    if market.startswith("OVER_") or market.startswith("UNDER_"):
        return "totals"

    if market in {"BTTS_YES", "BTTS_NO"}:
        return "btts"

    return "unknown"


def outcome_name_for_closing(match, market):
    if market == "HOME_WIN":
        return match.get("home_team") or match.get("home")

    if market == "AWAY_WIN":
        return match.get("away_team") or match.get("away")

    if market == "DRAW":
        return "Draw"

    if market == "DOUBLE_1X":
        return "Home/Draw"

    if market == "DOUBLE_X2":
        return "Draw/Away"

    if market == "DOUBLE_12":
        return "Home/Away"

    if market.startswith("OVER_"):
        return "Over"

    if market.startswith("UNDER_"):
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

        "OVER_0.5": ["OVER_0.5", "UNDER_0.5"],
        "UNDER_0.5": ["OVER_0.5", "UNDER_0.5"],

        "OVER_1.5": ["OVER_1.5", "UNDER_1.5"],
        "UNDER_1.5": ["OVER_1.5", "UNDER_1.5"],

        "OVER_2.5": ["OVER_2.5", "UNDER_2.5"],
        "UNDER_2.5": ["OVER_2.5", "UNDER_2.5"],

        "OVER_3.5": ["OVER_3.5", "UNDER_3.5"],
        "UNDER_3.5": ["OVER_3.5", "UNDER_3.5"],

        "OVER_4.5": ["OVER_4.5", "UNDER_4.5"],
        "UNDER_4.5": ["OVER_4.5", "UNDER_4.5"],
    }

    # Double chance markets overlap, so standard margin sum is not meaningful.
    # We do not use margin rejection for these; calculate_market_margin returns 1.0.
    if market in {"DOUBLE_1X", "DOUBLE_X2", "DOUBLE_12"}:
        return ["DOUBLE_1X", "DOUBLE_X2", "DOUBLE_12"]

    return groups.get(market)


def _valid_decimal_odds(value):
    try:
        odd = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(odd) or odd <= 1.0:
        return None
    return odd


def calculate_market_margin_detail(odds_dict, market, execution_bookmaker=None):
    """Return a complete complementary market from exactly one bookmaker."""
    if market in DISABLED_AUTOMATIC_MARKETS:
        return None
    group = get_market_group(market)
    if not group:
        return None

    books_by_outcome = []
    for outcome in group:
        data = odds_dict.get(outcome)
        if not isinstance(data, dict):
            return None
        mapping = data.get("by_bookmaker")
        if not isinstance(mapping, dict) or not mapping:
            return None
        valid = {}
        for book, raw in mapping.items():
            bookmaker = str(book).strip()
            odd = _valid_decimal_odds(raw)
            if bookmaker and odd is not None:
                valid[bookmaker] = odd
        if not valid:
            return None
        books_by_outcome.append(valid)

    common = set(books_by_outcome[0])
    for mapping in books_by_outcome[1:]:
        common.intersection_update(mapping)
    if not common:
        return None

    if execution_bookmaker:
        bookmaker = str(execution_bookmaker).strip()
        if bookmaker not in common:
            return None
    else:
        bookmaker = min(
            common,
            key=lambda book: sum(1.0 / mapping[book] for mapping in books_by_outcome),
        )

    prices = {
        outcome: books_by_outcome[index][bookmaker]
        for index, outcome in enumerate(group)
    }
    overround = sum(1.0 / odd for odd in prices.values())
    if not math.isfinite(overround) or overround <= 0:
        return None
    observed_at = str(
        odds_dict.get(market, {}).get("observed_at")
        or datetime.now(timezone.utc).isoformat()
    )
    return MarketMargin(bookmaker, overround, prices, observed_at)


def calculate_market_margin(odds_dict, market, execution_bookmaker=None):
    detail = calculate_market_margin_detail(odds_dict, market, execution_bookmaker)
    return detail.overround if detail else None


def is_fresh_observation(value, max_age_seconds=300):
    try:
        observed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            return False
        age = (datetime.now(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds()
        return 0 <= age <= max(1, int(max_age_seconds))
    except (TypeError, ValueError, OverflowError):
        return False


def remove_margin(book_prob, margin_sum):
    if not margin_sum or margin_sum <= 0:
        return None
    return book_prob / margin_sum


def blend_probability(model_prob, true_book_prob, model_weight, market_weight):
    """Compatibility wrapper: market data never enters the bot's own odds."""
    return strict_probability(model_prob)


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


def make_pick_id(match, market, book_odds, bookmaker="", strategy_version="strict-v1"):
    raw = "|".join([
        str(match.get("fixture_id", "")),
        str(bookmaker),
        str(market),
        str(book_odds),
        str(strategy_version),
    ])

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def safe_match_value(match, *keys, default=""):
    for key in keys:
        value = match.get(key)

        if value not in [None, ""]:
            return value

    return default


def configure_bot_mode(mode="main"):
    global ALL_FILE, HISTORY_FILE
    mode = str(mode or "main").lower()
    if mode not in BOT_MODE_SETTINGS:
        mode = "main"
    settings = BOT_MODE_SETTINGS[mode]
    ALL_FILE = DATA_DIR / settings["all_file"]
    HISTORY_FILE = DATA_DIR / settings["history_file"]
    return mode, settings


def preserve_existing_file_when_empty():
    if ALL_FILE.exists() and ALL_FILE.stat().st_size > 10:
        try:
            old_rows = pd.read_csv(ALL_FILE)
            if not old_rows.empty:
                print("Brak nowych typow - zachowuje poprzedni niepusty plik typow")
                return
        except Exception:
            pass

    pd.DataFrame([]).to_csv(ALL_FILE, index=False)
    print("Brak typow i brak starego niepustego pliku - utworzono pusty CSV")

def strict_probability(value):
    try:
        probability = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(probability) or not 0.0 < probability < 1.0:
        return None
    return probability


def clamp_probability(value):
    """Backward-compatible name with strict, non-fabricating semantics."""
    return strict_probability(value)


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

    if engines.get("tempo"):
        tempo = engines.get("tempo").calculate_tempo(
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
    verified_model_probability = strict_probability(model_prob)
    if verified_model_probability is None:
        return None

    # Helper engines are observational until independently validated with
    # walk-forward data. They cannot alter production fair odds.
    xg_probability = None
    xg_engine = engines.get("xg") if isinstance(engines, dict) else None
    if xg_engine and home_xg is not None and away_xg is not None:
        try:
            xg_probability = strict_probability(
                xg_engine.calculate_probability(home_xg, away_xg)
            )
        except Exception:
            xg_probability = None

    final_probability = verified_model_probability
    fair_odds_model = 1 / verified_model_probability
    fair_odds_final = 1 / final_probability

    return {
        "blended_prob": verified_model_probability,
        "xg_probability": xg_probability,
        "bayesian_probability": None,
        "ensemble_probability": None,
        "final_probability": final_probability,
        "fair_odds_model": fair_odds_model,
        "fair_odds_final": fair_odds_final,
        "bookmaker_used_in_own_odds": False,
        "calibration_applied": False,
    }


def stage_ev(engines, final_probability, book_odds):
    if engines.get("value"):
        try:
            # market_value_engine returns percent value
            ev_percent = engines.get("value").calculate_ev(final_probability, book_odds)
            return ev_percent / 100
        except Exception:
            pass

    return (book_odds * final_probability) - 1


def stage_movement(engines, book_odds, opening_odds=None):
    opening_odds = safe_float(opening_odds, book_odds)

    if engines.get("movement"):
        try:
            return engines.get("movement").calculate_movement(
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
    if engines.get("filter"):
        try:
            # UWAGA: nie blokujemy agresywnie, ĹĽeby nie wyzerowaÄ‡ bota.
            return engines.get("filter").should_accept_pick(
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
    if engines.get("bankroll"):
        try:
            stake = engines.get("bankroll").recommended_stake(
                bankroll=bankroll,
                probability=probability,
                odds=odds,
                fraction=0.10,
                max_percent=0.25
            )
            fraction = engines.get("bankroll").kelly_fraction(probability, odds)
            return stake, fraction
        except Exception:
            pass

    fraction = kelly_fraction(probability, odds)
    return round(min(bankroll * fraction * 0.10, bankroll * 0.0025), 2), fraction


def stage_risk(engines, confidence_percent, ev_percent, tempo_level, fallback_risk):
    if engines.get("risk"):
        try:
            return engines.get("risk").risk_label(
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

    if engines.get("clv"):
        try:
            clv = engines.get("clv").calculate_clv(book_odds, closing_odds)
            return clv, engines.get("clv").clv_status(clv)
        except Exception:
            pass

    return 0, "PENDING_CLV"


# =========================
# MAIN BOT
# =========================

def run_bot(mode="main"):
    mode, mode_settings = configure_bot_mode(mode)
    print("=== BOT START: CORE + STAGES 1-10 INTEGRATED ===")
    print(f"BOT MODE: {mode_settings['label']} | output={ALL_FILE.name}")

    cfg = load_config(profile_override=mode_settings.get("profile"))
    filters = cfg["filters"]
    model_weight = cfg["model"]["model_weight"]
    market_weight = cfg["model"]["market_weight"]
    active_markets = cfg["active_markets"]
    thresholds = cfg["risk_thresholds"]
    bankroll_size = safe_float(cfg.get("bankroll", 1000), 1000)
    active_profile = str(cfg.get("active_filter_profile", "medium")).upper()
    print(
        f"FILTER PROFILE: {active_profile} | odds "
        f"{safe_float(filters.get('min_book_odds'), 1.0):.2f}-"
        f"{safe_float(filters.get('max_book_odds'), 3.5):.2f}"
    )

    engines = build_stage_engines()

    stage_a = StageAValueLayer()
    stage_b = StageBModelLayer()
    stage_c = StageCMetaLayer()

    print("âś… STAGE ENGINES:")
    for name, engine in engines.items():
        print(f" - {name}: {'ON' if engine else 'OFF'}")

    matches = get_matches()

    print(f"âś… MECZE: {len(matches)}")
    print("đź”Ž SAMPLE:", matches[:3])

    rows = []
    skip_stats = {
        "no_odds": 0,
        "no_xg": 0,
        "inactive_market": 0,
        "disabled_market": 0,
        "stale_odds": 0,
        "no_model_prob": 0,
        "odds_range": 0,
        "margin": 0,
        "edge_ev": 0,
        "risk_skip": 0,
        "stage_filter_rejected": 0,
    }

    if not matches:
        print("âš ď¸Ź BRAK MECZĂ“W Z API â€” nie nadpisujÄ™ starego CSV")
        preserve_existing_file_when_empty()
        append_event("prematch_empty_selection", {"mode": mode, "reason": "filters_or_no_value", "output_file": str(ALL_FILE)}, source="bot.py")
        print(f"đź“ SKIP STATS: {skip_stats}")
        print("âś… GOTOWE")
        print("đź“Š 0 nowych typĂłw zapisanych")
        print(f"đź“ {ALL_FILE}")
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

            # =========================
            # TARGET MARKETS ONLY
            # 1X / X2 / 12, BTTS, Over/Under 0.5â€“4.5
            # =========================
            if market not in TARGET_MARKETS:
                continue

            if market in DISABLED_AUTOMATIC_MARKETS:
                skip_stats["disabled_market"] += 1
                continue

            if not active_markets.get(market, True):
                skip_stats["inactive_market"] += 1
                continue

            model_prob = strict_probability(model.get(market))

            if model_prob is None:
                skip_stats["no_model_prob"] += 1
                continue

            book_odds = _valid_decimal_odds(data.get("best_odds"))
            bookmaker = data.get("bookmaker", data.get("site", ""))

            if not is_fresh_observation(
                data.get("observed_at"),
                os.getenv("BETBOT_MAX_ODDS_AGE_SECONDS", "300"),
            ):
                skip_stats["stale_odds"] += 1
                continue

            # =========================
            # ODDS RANGE FILTER
            # =========================
            min_book_odds = safe_float(filters.get("min_book_odds"), 1.00)
            max_book_odds = safe_float(filters.get("max_book_odds"), 3.50)

            if book_odds is None or book_odds < min_book_odds or book_odds > max_book_odds:
                skip_stats["odds_range"] += 1
                continue

            margin_detail = calculate_market_margin_detail(
                odds_data,
                market,
                execution_bookmaker=bookmaker,
            )
            margin_sum = margin_detail.overround if margin_detail else None

            if not margin_sum or margin_sum > filters["max_margin_sum"]:
                skip_stats["margin"] += 1
                continue

            book_prob = 1 / book_odds
            true_book_prob = remove_margin(book_prob, margin_sum)

            true_book_prob = strict_probability(true_book_prob)
            if true_book_prob is None:
                skip_stats["margin"] += 1
                continue

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

            if probability_data is None:
                skip_stats["no_model_prob"] += 1
                continue

            final_prob = probability_data["final_probability"]

            stage_a_data = stage_a.enrich_pick(
                pick={},
                probability=final_prob,
                league=match.get("league", ""),
                market=market,
                opening_odds=data.get("opening_odds"),
                current_odds=book_odds,
                market_avg_odds=data.get("market_avg_odds"),
                pinnacle_odds=data.get("pinnacle_odds"),
                betfair_odds=data.get("betfair_odds")
            )

            stage_b_data = stage_b.enrich_pick(
                pick={},
                probability=final_prob,
                home_xg=home_xg,
                away_xg=away_xg,
                minute=match.get("minute", 0),
                shots_on_target=match.get("shots_on_target", 0),
                dangerous_attacks=match.get("dangerous_attacks", 0),
                possession=match.get("possession", 50),
                pressure=pressure,
                corners=match.get("corners", 0),
                sharp_score=stage_a_data.get("sharp_score", 0),
                clv_score=0
            )

            fair_odds_model = probability_data["fair_odds_model"]
            fair_odds_final = probability_data["fair_odds_final"]

            edge = final_prob - true_book_prob
            edge_relative = (final_prob / true_book_prob) - 1
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
            fractional_kelly = min(full_kelly * 0.10, 0.0025)

            recommended_stake, stage_kelly_fraction = stage_bankroll(
                engines,
                bankroll_size,
                final_prob,
                book_odds
            )

            stage_c_data = stage_c.enrich_pick(
                pick={},
                market=market,
                model_prob=model_prob,
                market_prob=true_book_prob,
                xg_prob=stage_b_data.get("advanced_over25_prob"),
                momentum_prob=stage_b_data.get("confidence_calibrated_v2"),
                sharp_prob=stage_a_data.get("stage_a_probability"),
                base_stake=recommended_stake,
                confidence=confidence_percent,
                ev=ev_percent,
                risk_label=risk_level,
                sharp_score=stage_a_data.get("sharp_score", 0),
                clv_percent=0,
                momentum_score=stage_b_data.get("momentum_score", 0)
            )

            # =========================
            # PROFESSIONAL PICK SCORE
            # =========================
            meta_prob_score = safe_float(stage_c_data.get("meta_probability", 0), 0)
            sharp_score_ai = safe_float(stage_a_data.get("sharp_score", 0), 0)
            momentum_score_ai = safe_float(stage_b_data.get("momentum_score", 0), 0)
            calibrated_score_ai = safe_float(
                stage_b_data.get("confidence_calibrated_v2", confidence_percent),
                confidence_percent
            )

            # Decision score uses only the verified model and execution market.
            # Stage A/B/C remain diagnostics and cannot upgrade a recommendation.
            ai_pick_score = round(
                (confidence_percent * 0.50)
                + (min(max(ev, 0.0), 0.25) / 0.25 * 25.0)
                + (min(max(edge, 0.0), 0.15) / 0.15 * 25.0),
                2,
            )

            # =========================
            # PROFESSIONAL PICK RANKING
            # =========================
            if ai_pick_score >= 75:
                best_pick_label = "TOP PICK"

            elif ai_pick_score >= 65:
                best_pick_label = "BEST PICK"

            elif ai_pick_score >= 50:
                best_pick_label = "VALUE PICK"

            else:
                best_pick_label = "STANDARD"

            best_pick = best_pick_label != "STANDARD"

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
            strategy_version = os.getenv("BETBOT_STRATEGY_VERSION", "strict-v1")
            pick_id = make_pick_id(match, market, book_odds, bookmaker, strategy_version)

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

                "data": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "decision_at": datetime.now(timezone.utc).isoformat(),
                "strategy_version": strategy_version,
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
                "kelly_10": round(fractional_kelly, 4),
                "kelly_25": round(fractional_kelly, 4),
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
                "margin_bookmaker": margin_detail.bookmaker,
                "margin_prices": json.dumps(margin_detail.prices, ensure_ascii=False, sort_keys=True),
                "odds_observed_at": margin_detail.observed_at,
                "edge_probability": round(edge, 4),
                "edge_relative": round(edge_relative, 4),
                "expected_return": round(ev, 4),
                "bookmaker_used_in_own_odds": False,
                "calibration_applied": False,
                "betting_enabled": os.getenv("BETTING_ENABLED", "false").strip().lower() == "true",
                "execution_status": "PROPOSED_ONLY",
                "decision_basis": "VERIFIED_MODEL_PLUS_SAME_BOOKMAKER_MARKET",
                "auxiliary_stages_decision_authority": False,
                "risk_level": risk_level,
                "ai_risk": ai_risk,
                "risk": ai_risk,
                "sharp_score": stage_a_data.get("sharp_score"),
                "sharp_label": stage_a_data.get("sharp_label"),
                "sharp_signals": stage_a_data.get("sharp_signals"),
                "stage_a_probability": stage_a_data.get("stage_a_probability"),

                "advanced_total_xg": stage_b_data.get("advanced_total_xg"),
                "advanced_over25_prob": stage_b_data.get("advanced_over25_prob"),
                "momentum_score": stage_b_data.get("momentum_score"),
                "momentum_label": stage_b_data.get("momentum_label"),
                "confidence_calibrated_v2": stage_b_data.get("confidence_calibrated_v2"),

                "meta_probability": stage_c_data.get("meta_probability"),
                "meta_weight_model": stage_c_data.get("meta_weight_model"),
                "meta_weight_market": stage_c_data.get("meta_weight_market"),
                "meta_weight_xg": stage_c_data.get("meta_weight_xg"),
                "meta_weight_momentum": stage_c_data.get("meta_weight_momentum"),
                "meta_weight_sharp": stage_c_data.get("meta_weight_sharp"),
                "dynamic_stake": stage_c_data.get("dynamic_stake"),

                "ai_pick_score": ai_pick_score,
                "best_pick": best_pick,
                "best_pick_label": best_pick_label,
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

        df["bot_mode"] = mode
        df["bot_label"] = mode_settings["label"]
        if os.getenv("BETBOT_QUALITY_SHADOW", "0").strip().lower() in {"1", "true", "yes", "on"}:
            try:
                from quality_live_shadow import record_live_shadow
                for shadow_pick in df.to_dict("records"):
                    record_live_shadow(
                        shadow_pick,
                        {
                            "market": shadow_pick.get("market"),
                            "probability": shadow_pick.get("prawd_final"),
                            "odds": shadow_pick.get("odds"),
                            "bookmaker_odds": shadow_pick.get("odds"),
                        },
                    )
            except Exception as shadow_exc:
                print(f"[QUALITY LIVE SHADOW ERROR] {shadow_exc}")
        df.to_csv(ALL_FILE, index=False)
        append_records(f"prematch_{mode}_picks", df.to_dict("records"), source="bot.py")
        append_event("prematch_cycle", {"mode": mode, "picks": int(len(df)), "file": str(ALL_FILE)}, source="bot.py")

        if HISTORY_FILE.exists():
            df.to_csv(HISTORY_FILE, mode="a", index=False, header=False)
        else:
            df.to_csv(HISTORY_FILE, index=False)

    else:
        preserve_existing_file_when_empty()
        append_event("prematch_empty_selection", {"mode": mode, "reason": "filters_or_no_value", "output_file": str(ALL_FILE)}, source="bot.py")

    print(f"đź“ SKIP STATS: {skip_stats}")
    print("âś… GOTOWE")
    print(f"đź“Š {len(df)} typĂłw zapisanych")
    print(f"đź“ {ALL_FILE}")
    print("âś… ETAPY AKTYWNE: tempo, confidence, xg, market movement, bayesian, ensemble, filter, bankroll, clv, stage_a, stage_b, stage_c, target_markets, best_pick_ranking")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run BetBot prematch mode")
    parser.add_argument("--mode", choices=sorted(BOT_MODE_SETTINGS), default="main")
    args = parser.parse_args()
    run_bot(mode=args.mode)
