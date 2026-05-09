import pandas as pd
from data_api import get_matches, get_odds_market_data

ALL_FILE = "/app/data/auto_all_picks.csv"


def run_bot():

    print("[BOT] === BOT START: CORE + LOOP READY + RISK LEVELS ===")

    try:

        matches = get_matches()

    except Exception as e:

        print(f"[BOT] FETCH ERROR: {e}")

        matches = []

    print(f"[BOT] MECZE: {len(matches)}")

    rows = []

    skip_stats = {
        "rejected": 0
    }

    if not matches:

        print("⚠️ BRAK MECZÓW Z API — sprawdź logi data_api.py powyżej")

        pd.DataFrame(rows).to_csv(ALL_FILE, index=False)

        print(f"📈 SKIP STATS: {skip_stats}")
        print("✅ GOTOWE")
        print("📊 0 typów zapisanych")
        print(f"📁 {ALL_FILE}")

        return

    for match in matches:

        try:

            row = {
                "home": match.get("home", ""),
                "away": match.get("away", ""),
                "league": match.get("league", ""),
                "minute": match.get("minute", ""),
                "score": match.get("score", ""),
                "signal": match.get("signal", ""),
                "confidence": match.get("confidence", 0),
                "ev": match.get("ev", 0),
                "odds": match.get("odds", 0),
                "status": match.get("status", ""),
                "market": match.get("market", ""),
                "pressure": match.get("pressure", 0),
                "momentum": match.get("momentum", 0),
            }

            rows.append(row)

        except Exception as e:

            print(f"[BOT] MATCH PARSE ERROR: {e}")

            continue

    df = pd.DataFrame(rows)

    df.to_csv(ALL_FILE, index=False)

    print(f"[BOT] SAMPLE: {rows[:1]}")
    print("✅ GOTOWE")
    print(f"📊 {len(rows)} typów zapisanych")
    print(f"📁 {ALL_FILE}")


if __name__ == "__main__":
    run_bot()
