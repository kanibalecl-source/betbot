from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from persistent_storage import init_storage, log_learning_event, summary, upsert_pick

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

SOURCES = [
    ("PREMATCH", DATA_DIR / "auto_all_picks.csv"),
    ("AI_PICKS", DATA_DIR / "ai_picks.csv"),
    ("LIVE", DATA_DIR / "live_matches.csv"),
]


def read_csv_safe(path: Path) -> pd.DataFrame:
    try:
        if path.exists() and path.stat().st_size > 0:
            return pd.read_csv(path)
    except Exception as exc:
        print(f"[PERSISTENCE] CSV READ ERROR {path}: {exc}", flush=True)
    return pd.DataFrame()


def sync_once() -> dict:
    init_storage()
    saved = 0
    details = {}
    for source, path in SOURCES:
        df = read_csv_safe(path)
        details[source] = len(df)
        if df.empty:
            continue
        for _, row in df.iterrows():
            try:
                upsert_pick(row.to_dict(), source=source)
                saved += 1
            except Exception as exc:
                print(f"[PERSISTENCE] UPSERT ERROR {source}: {exc}", flush=True)
    state = summary()
    state.update({"saved_this_cycle": saved, "source_rows": details, "updated_at": datetime.utcnow().isoformat()})
    log_learning_event("persistence_sync", state)
    print(f"[PERSISTENCE] OK {state}", flush=True)
    return state


def main() -> None:
    interval = 120
    print("[PERSISTENCE] START", flush=True)
    while True:
        try:
            sync_once()
        except Exception as exc:
            print(f"[PERSISTENCE] LOOP ERROR: {exc}", flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
