from pathlib import Path
import pandas as pd
from config import BANKROLL

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

BETS_FILE = DATA_DIR / "bets.csv"

# 🔥 NOWY LIMIT
MAX_ACTIVE_BETS = 35


def load_active_bets():
    if not BETS_FILE.exists():
        return pd.DataFrame()

    df = pd.read_csv(BETS_FILE)

    # aktywne = bez wyniku
    if "result" in df.columns:
        df = df[df["result"].isna()]

    return df


def can_add_bet(league, stake, match=None, bankroll=BANKROLL):
    active_bets = load_active_bets()

    # 🔥 LIMIT 35 WEJŚĆ
    if len(active_bets) >= MAX_ACTIVE_BETS:
        return False, "MAX BETS REACHED"

    # 🔥 LIMIT RYZYKA (opcjonalny)
    total_staked = active_bets["stake"].sum() if not active_bets.empty else 0

    if total_staked + stake > bankroll * 0.5:
        return False, "TOO MUCH RISK"

    return True, "OK"