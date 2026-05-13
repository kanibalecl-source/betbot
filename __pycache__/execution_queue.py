import pandas as pd
from pathlib import Path
from datetime import datetime

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
QUEUE_FILE = DATA_DIR / "execution_queue.csv"
APPROVED_FILE = DATA_DIR / "approved_bets.csv"

def add_to_queue(row: dict):
    row["queued_at"] = datetime.now()
    df_new = pd.DataFrame([row])
    if QUEUE_FILE.exists():
        df_old = pd.read_csv(QUEUE_FILE)
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new
    df.to_csv(QUEUE_FILE, index=False)

def approve_bet(fixture_id: int, market: str):
    if not QUEUE_FILE.exists():
        return
    df = pd.read_csv(QUEUE_FILE)
    if df.empty:
        return
    mask = (df["fixture_id"] == fixture_id) & (df["market"] == market)
    selected = df[mask].copy()
    remaining = df[~mask].copy()
    if selected.empty:
        return
    selected["approved_at"] = datetime.now()
    if APPROVED_FILE.exists():
        old = pd.read_csv(APPROVED_FILE)
        selected = pd.concat([old, selected], ignore_index=True)
    selected.to_csv(APPROVED_FILE, index=False)
    remaining.to_csv(QUEUE_FILE, index=False)
