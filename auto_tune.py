import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from database import get_conn, init_db

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config_strategy.json"
LOG_FILE = BASE_DIR / "data" / "autotune_log.txt"


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def log(msg):
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} | {msg}\n")


def main():
    init_db()
    cfg = load_config()

    if not cfg.get("autotune", {}).get("enabled", False):
        print("Autotune wyłączony.")
        return

    min_bets = cfg["autotune"]["min_bets_per_market"]
    roi_limit = cfg["autotune"]["disable_market_if_roi_below"]
    clv_limit = cfg["autotune"]["disable_market_if_clv_below"]

    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM bets WHERE status = 'CLOSED'", conn)
    conn.close()

    if df.empty:
        print("Brak danych do autotune.")
        return

    grouped = df.groupby("market").agg(
        bets=("id", "count"),
        stake=("stake", "sum"),
        profit=("profit", "sum"),
        avg_clv=("clv", "mean")
    ).reset_index()

    grouped["roi"] = grouped["profit"] / grouped["stake"]

    changed = False

    for _, row in grouped.iterrows():
        market = row["market"]

        if row["bets"] < min_bets:
            continue

        bad_roi = row["roi"] < roi_limit
        bad_clv = pd.notna(row["avg_clv"]) and row["avg_clv"] < clv_limit

        if bad_roi or bad_clv:
            if cfg["active_markets"].get(market, True):
                cfg["active_markets"][market] = False
                changed = True
                log(f"WYŁĄCZONO {market} | bets={row['bets']} roi={row['roi']:.4f} clv={row['avg_clv']}")

    if changed:
        save_config(cfg)
        print("Autotune: wprowadzono zmiany w config_strategy.json")
    else:
        print("Autotune: brak zmian.")


if __name__ == "__main__":
    main()
