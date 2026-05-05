import pandas as pd
from pathlib import Path
from config import BANKROLL

DATA_DIR = Path("data")
RESULTS_FILE = DATA_DIR / "results.csv"

def get_drawdown(bankroll=BANKROLL):
    if not RESULTS_FILE.exists():
        return 0.0
    df = pd.read_csv(RESULTS_FILE)
    if df.empty or "profit" not in df.columns:
        return 0.0
    df["profit"] = pd.to_numeric(df["profit"], errors="coerce").fillna(0)
    equity = bankroll + df["profit"].cumsum()
    peak = equity.cummax()
    dd = ((equity - peak) / peak).min()
    return round(dd * 100, 2)

def get_mode():
    dd = get_drawdown()
    if dd < -30:
        return "STOP"
    if dd < -20:
        return "DEFENSIVE"
    if dd < -10:
        return "REDUCED"
    return "NORMAL"
