import pandas as pd
import requests
from pathlib import Path

API_KEY = "272be17b5c62994697794e6fc017996c".strip()
BASE_URL = "https://v3.football.api-sports.io"

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PICKS_FILE = DATA_DIR / "auto_all_picks.csv"
HISTORY_FILE = DATA_DIR / "history_results.csv"


def _headers():
    return {"x-apisports-key": API_KEY}


def load_picks():
    if not PICKS_FILE.exists():
        return pd.DataFrame()
    return pd.read_csv(PICKS_FILE)


def load_history():
    if not HISTORY_FILE.exists():
        return pd.DataFrame()
    return pd.read_csv(HISTORY_FILE)


def fetch_fixture_result(fixture_id):
    r = requests.get(
        f"{BASE_URL}/fixtures",
        headers=_headers(),
        params={"id": fixture_id},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()

    if not data.get("response"):
        return None

    g = data["response"][0]
    goals_home = g["goals"]["home"]
    goals_away = g["goals"]["away"]
    status = g["fixture"]["status"]["short"]

    return {
        "status": status,
        "home_goals": goals_home,
        "away_goals": goals_away,
        "total_goals": goals_home + goals_away,
    }


def settle_bet(kod_rynku, result):
    hg = result["home_goals"]
    ag = result["away_goals"]
    tg = result["total_goals"]

    if kod_rynku == "HOME_WIN":
        return "WIN" if hg > ag else "LOSE"
    if kod_rynku == "DRAW":
        return "WIN" if hg == ag else "LOSE"
    if kod_rynku == "AWAY_WIN":
        return "WIN" if ag > hg else "LOSE"

    if kod_rynku == "HOME_OR_DRAW":
        return "WIN" if hg >= ag else "LOSE"
    if kod_rynku == "AWAY_OR_DRAW":
        return "WIN" if ag >= hg else "LOSE"
    if kod_rynku == "HOME_OR_AWAY":
        return "WIN" if hg != ag else "LOSE"

    if kod_rynku == "BTTS_YES":
        return "WIN" if hg > 0 and ag > 0 else "LOSE"
    if kod_rynku == "BTTS_NO":
        return "WIN" if hg == 0 or ag == 0 else "LOSE"

    if kod_rynku.startswith("OVER_"):
        line = float(kod_rynku.split("_")[1])
        return "WIN" if tg > line else "LOSE"

    if kod_rynku.startswith("UNDER_"):
        line = float(kod_rynku.split("_")[1])
        return "WIN" if tg < line else "LOSE"

    return "UNKNOWN"


def calculate_pnl(row, settlement):
    stake = float(row.get("stawka_pln", 0) or 0)
    odds = float(row.get("kurs_buk", 0) or 0)

    if settlement == "WIN":
        return round(stake * (odds - 1), 2)
    if settlement == "LOSE":
        return round(-stake, 2)
    return 0.0


def update_results():
    picks = load_picks()
    if picks.empty:
        print("Brak picków")
        return

    history = load_history()
    existing_keys = set()

    if not history.empty:
        existing_keys = set(
            history["fixture_id"].astype(str) + "|" + history["kod_rynku"].astype(str)
        )

    rows = []

    for _, row in picks.iterrows():
        key = f"{row['fixture_id']}|{row['kod_rynku']}"
        if key in existing_keys:
            continue

        result = fetch_fixture_result(int(row["fixture_id"]))
        if result is None:
            continue

        if result["status"] not in ["FT", "AET", "PEN"]:
            continue

        settlement = settle_bet(str(row["kod_rynku"]), result)
        pnl = calculate_pnl(row, settlement)

        out = row.to_dict()
        out["wynik_meczu"] = f"{result['home_goals']}:{result['away_goals']}"
        out["settlement"] = settlement
        out["pnl"] = pnl
        rows.append(out)

    if rows:
        new_df = pd.DataFrame(rows)
        final = pd.concat([history, new_df], ignore_index=True) if not history.empty else new_df
        final.to_csv(HISTORY_FILE, index=False)
        print("Zaktualizowano historię:", len(rows))
    else:
        print("Brak nowych rozliczeń")


if __name__ == "__main__":
    update_results()