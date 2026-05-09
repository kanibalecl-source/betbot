from pathlib import Path
import pandas as pd
from auto_optimizer import AutoOptimizer

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_FILE = DATA_DIR / "results_history.csv"


def generate_optimizer_report():

    if not RESULTS_FILE.exists():
        print("NO RESULTS HISTORY")
        return

    df = pd.read_csv(RESULTS_FILE)

    optimizer = AutoOptimizer()

    print("=== BEST LEAGUES ===")
    print(optimizer.best_leagues(df))

    print("=== BEST MARKETS ===")
    print(optimizer.best_markets(df))

    print("=== RECOMMENDED THRESHOLDS ===")
    print(optimizer.recommended_thresholds(df))


if __name__ == "__main__":
    generate_optimizer_report()
