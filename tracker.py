import pandas as pd
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
BETS_FILE = DATA_DIR / "bets_log.csv"
RESULTS_FILE = DATA_DIR / "results.csv"
CLV_FILE = DATA_DIR / "clv_log.csv"

def append_row(file_path: Path, row: dict):
    df_new = pd.DataFrame([row])
    if file_path.exists():
        df_old = pd.read_csv(file_path)
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new
    df.to_csv(file_path, index=False)

def log_bet(row: dict):
    append_row(BETS_FILE, row)

def settle_bets_from_results(api_results: list[dict]):
    if not BETS_FILE.exists():
        return
    bets = pd.read_csv(BETS_FILE)
    if bets.empty:
        return
    existing = pd.read_csv(RESULTS_FILE) if RESULTS_FILE.exists() and RESULTS_FILE.stat().st_size > 0 else pd.DataFrame()
    results_index = {r["fixture_id"]: r for r in api_results}
    settled_rows = []

    for _, bet in bets.iterrows():
        fixture_id = bet.get("fixture_id")
        if pd.isna(fixture_id):
            continue
        fixture_id = int(fixture_id)
        market = str(bet.get("market", ""))
        team = str(bet.get("team", ""))
        if not existing.empty:
            mask = (existing.get("fixture_id") == fixture_id) & (existing.get("market") == market) & (existing.get("team") == team)
            if mask.any():
                continue
        if fixture_id not in results_index:
            continue
        result_data = results_index[fixture_id]
        if not result_data["finished"]:
            continue

        home_goals = result_data["home_goals"]
        away_goals = result_data["away_goals"]
        total_goals = home_goals + away_goals
        match = str(bet.get("match", ""))
        result = "lose"

        if market == "HOME_WIN":
            home_team = match.split(" vs ")[0]
            if team == home_team and home_goals > away_goals:
                result = "win"
        elif market == "OVER_2_5":
            if total_goals > 2:
                result = "win"
        elif market == "BTTS_YES":
            if home_goals > 0 and away_goals > 0:
                result = "win"

        odds_taken = float(bet.get("odds_taken", bet.get("current_odds", 0)))
        profit = round((odds_taken - 1) if result == "win" else -1.0, 2)

        settled_rows.append({
            "date": datetime.now(),
            "fixture_id": fixture_id,
            "match": match,
            "league": bet.get("league", ""),
            "market": market,
            "team": team,
            "result": result,
            "profit": profit,
            "stake": bet.get("stake", 0),
            "stake_units": bet.get("stake_units", 0),
            "settled": True,
            "settled_at": datetime.now(),
        })

    if settled_rows:
        df = pd.DataFrame(settled_rows)
        if not existing.empty:
            df = pd.concat([existing, df], ignore_index=True)
        df.to_csv(RESULTS_FILE, index=False)

def update_clv_from_bets():
    if not BETS_FILE.exists():
        return
    bets = pd.read_csv(BETS_FILE)
    if bets.empty:
        return
    rows = []
    for _, bet in bets.iterrows():
        odds_taken = bet.get("odds_taken", bet.get("current_odds", None))
        closing_odds = bet.get("closing_odds", bet.get("current_odds", None))
        if pd.isna(odds_taken) or pd.isna(closing_odds):
            continue
        odds_taken = float(odds_taken)
        closing_odds = float(closing_odds)
        if odds_taken <= 0 or closing_odds <= 0:
            continue
        clv_ratio = round(closing_odds / odds_taken, 4)
        rows.append({
            "date": datetime.now(),
            "fixture_id": bet.get("fixture_id"),
            "match": bet.get("match"),
            "league": bet.get("league"),
            "market": bet.get("market"),
            "odds_taken": odds_taken,
            "closing_odds": closing_odds,
            "clv_ratio": clv_ratio,
        })
    if rows:
        pd.DataFrame(rows).to_csv(CLV_FILE, index=False)
