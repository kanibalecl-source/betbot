import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
FILE = DATA_DIR / "placed_bets.csv"


def load_bets():
    if not FILE.exists():
        return pd.DataFrame()
    return pd.read_csv(FILE)


def save_bets(df):
    df.to_csv(FILE, index=False)


def add_bet(row):
    df = load_bets()

    new = {
        "data": row["data"],
        "mecz": row["mecz"],
        "typ": row["typ"],
        "kurs": row["kurs"],
        "stawka": row["stawka"],
        "result": "OPEN",
        "pnl": 0
    }

    df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
    save_bets(df)


def settle_bet(index, result):
    df = load_bets()

    if index >= len(df):
        return

    stake = df.loc[index, "stawka"]
    odds = df.loc[index, "kurs"]

    if result == "WIN":
        pnl = stake * (odds - 1)
    else:
        pnl = -stake

    df.loc[index, "result"] = result
    df.loc[index, "pnl"] = round(pnl, 2)

    save_bets(df)