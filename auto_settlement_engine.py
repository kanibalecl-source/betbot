from shadow.shadow_logger import log_shadow_event
from pathlib import Path
import pandas as pd
from datetime import datetime

PICKS = Path("data/auto_all_picks.csv")
RESULTS = Path("data/results_history.csv")

def ensure_files():
    PICKS.parent.mkdir(exist_ok=True)
    if not PICKS.exists():
        pd.DataFrame(columns=[
            "date","match","market","odds","confidence"
        ]).to_csv(PICKS, index=False)

    if not RESULTS.exists():
        pd.DataFrame(columns=[
            "date","match","market","result","profit","roi","settled_at"
        ]).to_csv(RESULTS, index=False)

def settlement_snapshot():
    ensure_files()
    picks = pd.read_csv(PICKS)
    results = pd.read_csv(RESULTS)

    snapshot = {
        "picks": len(picks),
        "results": len(results),
        "updated": datetime.utcnow().isoformat()
    }

    return snapshot

if __name__ == "__main__":
    print("AUTO SETTLEMENT ENGINE ACTIVE")
    print(settlement_snapshot())
