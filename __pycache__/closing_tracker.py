import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
BETS_FILE = DATA_DIR / "bets_log.csv"
CLOSING_FILE = DATA_DIR / "closing_odds.csv"

def save_closing_odds(rows: list[dict]):
    if not rows:
        return
    df_new = pd.DataFrame(rows)
    if CLOSING_FILE.exists():
        df_old = pd.read_csv(CLOSING_FILE)
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new
    df.to_csv(CLOSING_FILE, index=False)

def update_bets_with_closing():
    if not BETS_FILE.exists() or not CLOSING_FILE.exists():
        return
    bets = pd.read_csv(BETS_FILE)
    closings = pd.read_csv(CLOSING_FILE)
    if bets.empty or closings.empty:
        return
    closings["timestamp"] = pd.to_datetime(closings["timestamp"], errors="coerce")
    latest_closing = closings.sort_values("timestamp").groupby(["fixture_id", "market"], as_index=False).last()
    merged = bets.merge(latest_closing[["fixture_id", "market", "closing_odds"]], on=["fixture_id", "market"], how="left", suffixes=("", "_new"))
    if "closing_odds_new" in merged.columns:
        if "closing_odds" not in merged.columns:
            merged["closing_odds"] = merged["closing_odds_new"]
        else:
            merged["closing_odds"] = merged["closing_odds_new"].combine_first(merged["closing_odds"])
        merged = merged.drop(columns=["closing_odds_new"])
    merged.to_csv(BETS_FILE, index=False)
