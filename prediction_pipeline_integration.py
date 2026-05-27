from shadow.shadow_logger import log_shadow_event
from pathlib import Path
import pandas as pd
from master_prediction_engine import MasterPredictionEngine

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

OUTPUT_FILE = DATA_DIR / "auto_all_picks.csv"
LIVE_FILE = DATA_DIR / "live_matches.csv"


def process_and_save_matches(matches, bankroll=1000, output_file=OUTPUT_FILE):
    """
    Centralna funkcja integracji ETAPÓW 1–10.

    Podłącz ją w miejscu, gdzie bot obecnie zapisuje typy do CSV.

    Przykład:
        from prediction_pipeline_integration import process_and_save_matches
        process_and_save_matches(matches)
    """

    engine = MasterPredictionEngine(bankroll=bankroll)

    processed = []

    for match in matches:
        result = engine.process_match(match)

        if result.get("filter_status") == "REJECTED":
            print(f"⚠️ PICK REJECTED: {result.get('filter_reason')} | {result.get('home')} vs {result.get('away')}")
            continue

        processed.append(result)

    df = pd.DataFrame(processed)

    df.to_csv(output_file, index=False)
    df.to_csv(LIVE_FILE, index=False)

    print(f"✅ MASTER PIPELINE SAVED -> {output_file}")
    print(f"✅ MASTER PIPELINE LIVE SAVED -> {LIVE_FILE}")
    print(f"✅ PICKS COUNT -> {len(df)}")

    return processed
