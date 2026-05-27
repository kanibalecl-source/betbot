from shadow.shadow_logger import log_shadow_event
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


# 🔥 LICZENIE MARŻY / OVERROUND DLA RYNKU 1X2
def calculate_market_margin(odds_dict):
    probs = []

    for market in ["HOME_WIN", "DRAW", "AWAY_WIN"]:
        data = odds_dict.get(market)
        if data:
            odd = data.get("best_odds")
            if odd and odd > 0:
                probs.append(1 / odd)

    if len(probs) < 2:
        return None

    return sum(probs)


# 🔥 USUWANIE MARŻY Z PRAWDOPODOBIEŃSTWA BUKMACHERA
def remove_margin(book_prob, margin_sum):
    if not margin_sum or margin_sum <= 0:
        return book_prob
    return book_prob / margin_sum


def run_bot():
    print("=== BOT START (FIXED MARGIN LOGIC) ===")

    matches = get_matches()
    rows = []

    for match in matches:

        odds_data = get_odds_market_data(match)
        if not odds_data:
            continue

        margin_sum = calculate_market_margin(odds_data)

        home_xg, away_xg = get_match_xg(match)
        if home_xg is None:
            continue

        model = build_model(home_xg, away_xg)

        for market, data in odds_data.items():

            prob = model.get(market)
            if not prob or prob <= 0:
                continue

            book_odds = data.get("best_odds")

            if not book_odds or book_odds < 1:
                continue

            # 🔥 PRAWDOPODOBIEŃSTWO Z KURSU BUKMACHERA
            book_prob = 1 / book_odds

            # 🔥 USUWAMY MARŻĘ Z BUKMACHERA, NIE Z MODELU
            true_book_prob = remove_margin(book_prob, margin_sum)

            # zabezpieczenia przed skrajnymi wartościami
            prob = min(max(prob, 0.01), 0.99)
            true_book_prob = min(max(true_book_prob, 0.01), 0.99)

            # 🔥 FAIR ODDS MODELU
            fair_odds = 1 / prob

            # 🔥 EDGE: MODEL VS OCZYSZCZONE PRAWDOPODOBIEŃSTWO BUKA
            edge = (prob / true_book_prob) - 1

            if edge < 0.03:
                continue

            league_full = f"{match['league']} / {match['country']}"

            rows.append({
                "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "liga": league_full,
                "mecz": match["match"],
                "typ": format_bet(market),

                "kurs_buk": round(book_odds, 2),
                "kurs_bota": round(fair_odds, 2),

                "prawd": round(prob, 3),
                "edge": round(edge, 4),

                "home_xg": home_xg,
                "away_xg": away_xg,

                "marza_%": round((margin_sum - 1) * 100, 2) if margin_sum else None
            })

    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.sort_values(by="edge", ascending=False)

    df.to_csv(ALL_FILE, index=False)

    print("✅ GOTOWE")
    print(f"📊 {len(df)} typów zapisanych")
    print(f"📁 {ALL_FILE}")


if __name__ == "__main__":
    run_bot()
