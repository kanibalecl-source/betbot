from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_FILE = DATA_DIR / "results_history.csv"
PICKS_HISTORY_FILE = DATA_DIR / "auto_all_picks_history.csv"


class AutoOptimizerV2:
    def load_history(self):
        if RESULTS_FILE.exists():
            return pd.read_csv(RESULTS_FILE)
        if PICKS_HISTORY_FILE.exists():
            return pd.read_csv(PICKS_HISTORY_FILE)
        return pd.DataFrame()

    def recommend_thresholds(self):
        df = self.load_history()
        if df.empty:
            return {"min_confidence": 65, "min_ev": 5, "min_edge": 3, "reason": "NO_HISTORY_DEFAULTS"}

        rec = {"min_confidence": 65, "min_ev": 5, "min_edge": 3, "reason": "DEFAULTS"}

        try:
            if "confidence" in df.columns:
                conf = pd.to_numeric(df["confidence"], errors="coerce").dropna()
                if len(conf) >= 50:
                    rec["min_confidence"] = int(max(55, min(80, conf.quantile(0.65))))

            if "ev_percent" in df.columns:
                ev = pd.to_numeric(df["ev_percent"], errors="coerce").dropna()
                if len(ev) >= 50:
                    rec["min_ev"] = round(max(2, min(12, ev.quantile(0.60))), 2)

            if "edge" in df.columns:
                edge = pd.to_numeric(df["edge"], errors="coerce").dropna()
                if len(edge) >= 50:
                    value = edge.quantile(0.60)
                    if abs(value) <= 1:
                        value *= 100
                    rec["min_edge"] = round(max(1, min(15, value)), 2)

            rec["reason"] = "HISTORY_BASED"
        except Exception as e:
            rec["reason"] = f"ERROR_{e}"

        return rec
