import json
import hashlib
import pandas as pd
from datetime import datetime
from pathlib import Path

from data_api import get_matches, get_odds_market_data
from model_goals import build_model
from team_stats import get_match_xg

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

ALL_FILE = DATA_DIR / "auto_all_picks.csv"
HISTORY_FILE = DATA_DIR / "auto_all_picks_history.csv"
CONFIG_FILE = BASE_DIR / "config_strategy.json"


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


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
        return match.get("home_team")
    if market == "AWAY_WIN":
        return match.get("away_team")
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


def run_bot():
    print("=== BOT START: CORE + LOOP READY + RISK LEVELS ===")

    cfg = load_config()
    filters = cfg["filters"]
    model_weight = cfg["model"]["model_weight"]
    market_weight = cfg["model"]["market_weight"]
    active_markets = cfg["active_markets"]
    thresholds = cfg["risk_thresholds"]

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

            model_prob = min(max(model_prob, 0.01), 0.99)
            true_book_prob = min(max(true_book_prob, 0.01), 0.99)

            final_prob = blend_probability(
                model_prob,
                true_book_prob,
                model_weight,
                market_weight
            )

            fair_odds_model = 1 / model_prob
            fair_odds_final = 1 / final_prob

            edge = (final_prob / true_book_prob) - 1
            ev = (book_odds * final_prob) - 1

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

            full_kelly = kelly_fraction(final_prob, book_odds)
            quarter_kelly = min(full_kelly * 0.25, 0.05)

            league_full = f"{match['league']} / {match.get('country', '')}"
            pick_id = make_pick_id(match, market, book_odds)

            rows.append({
                "pick_id": pick_id,
                "fixture_id": fixture_id,
                "odds_event_id": odds_event_id,
                "home_team": home_team,
                "away_team": away_team,
                "match_date": match_date,

                "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "liga": league_full,
                "mecz": match["match"],
                "market": market,
                "typ": format_bet(market),
                "bookmaker": bookmaker,

                "odds_api_market": market_to_odds_api(market),
                "closing_outcome_name": outcome_name_for_closing(match, market),

                "kurs_buk": round(book_odds, 2),
                "kurs_model": round(fair_odds_model, 2),
                "kurs_bota": round(fair_odds_final, 2),

                "prawd_model": round(model_prob, 4),
                "prawd_rynek": round(true_book_prob, 4),
                "prawd_final": round(final_prob, 4),

                "edge": round(edge, 4),
                "ev": round(ev, 4),

                "kelly_full": round(full_kelly, 4),
                "kelly_25": round(quarter_kelly, 4),

                "home_xg": round(home_xg, 3),
                "away_xg": round(away_xg, 3),

                "marza_sum": round(margin_sum, 4),
                "marza_%": round((margin_sum - 1) * 100, 2),
                "risk_level": risk_level,
                "status": "NEW"
            })

    df = pd.DataFrame(rows)

    if not df.empty:
        risk_order = {"TOP": 0, "LOW": 1, "RISK": 2}
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


if __name__ == "__main__":
    run_bot()
