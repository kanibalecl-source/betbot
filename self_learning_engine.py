from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

RESULTS_FILE = DATA_DIR / "results_history.csv"


class SelfLearningEngine:

    def load_results(self):

        try:
            if not RESULTS_FILE.exists():
                return pd.DataFrame()

            return pd.read_csv(RESULTS_FILE)

        except Exception as e:
            print(f"SELF LEARNING LOAD ERROR: {e}")
            return pd.DataFrame()


    def save_result(self, record):

        try:
            df_new = pd.DataFrame([record])

            if RESULTS_FILE.exists():
                df_old = pd.read_csv(RESULTS_FILE)
                df = pd.concat([df_old, df_new], ignore_index=True)
            else:
                df = df_new

            df.to_csv(RESULTS_FILE, index=False)

            print(f"✅ RESULT SAVED -> {RESULTS_FILE}")

        except Exception as e:
            print(f"SELF LEARNING SAVE ERROR: {e}")


    def league_performance(self):

        df = self.load_results()

        if df.empty or "league" not in df.columns or "profit" not in df.columns:
            return pd.DataFrame()

        return (
            df.groupby("league")
            .agg(
                bets=("profit", "count"),
                profit=("profit", "sum"),
                avg_profit=("profit", "mean")
            )
            .reset_index()
            .sort_values("profit", ascending=False)
        )


    def market_performance(self):

        df = self.load_results()

        if df.empty or "market" not in df.columns or "profit" not in df.columns:
            return pd.DataFrame()

        return (
            df.groupby("market")
            .agg(
                bets=("profit", "count"),
                profit=("profit", "sum"),
                avg_profit=("profit", "mean")
            )
            .reset_index()
            .sort_values("profit", ascending=False)
        )


    def confidence_buckets(self):

        df = self.load_results()

        if df.empty or "confidence" not in df.columns or "won" not in df.columns:
            return pd.DataFrame()

        df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce")
        df["bucket"] = pd.cut(
            df["confidence"],
            bins=[0, 50, 60, 70, 80, 90, 100],
            labels=["0-50", "50-60", "60-70", "70-80", "80-90", "90-100"]
        )

        return (
            df.groupby("bucket")
            .agg(
                bets=("won", "count"),
                hitrate=("won", "mean")
            )
            .reset_index()
        )
