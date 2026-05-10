from pathlib import Path
from datetime import datetime
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
CLV_FILE = DATA_DIR / "advanced_clv_history.csv"


class AdvancedCLVTracker:
    def calculate_clv_percent(self, odds_taken, closing_odds):
        try:
            odds_taken = float(odds_taken)
            closing_odds = float(closing_odds)
            if odds_taken <= 0 or closing_odds <= 0:
                return 0.0
            return round(((odds_taken / closing_odds) - 1) * 100, 2)
        except Exception:
            return 0.0

    def clv_label(self, clv_percent):
        try:
            clv_percent = float(clv_percent)
            if clv_percent >= 3:
                return "STRONG_POSITIVE_CLV"
            if clv_percent > 0:
                return "POSITIVE_CLV"
            if clv_percent <= -3:
                return "STRONG_NEGATIVE_CLV"
            if clv_percent < 0:
                return "NEGATIVE_CLV"
            return "NEUTRAL_CLV"
        except Exception:
            return "UNKNOWN"

    def build_record(self, pick_id="", match="", league="", market="", pick="", bookmaker="", odds_taken=0, closing_odds=0, confidence=0, ev=0):
        clv = self.calculate_clv_percent(odds_taken, closing_odds)
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "pick_id": pick_id,
            "match": match,
            "league": league,
            "market": market,
            "pick": pick,
            "bookmaker": bookmaker,
            "odds_taken": odds_taken,
            "closing_odds": closing_odds,
            "confidence": confidence,
            "ev": ev,
            "clv_percent": clv,
            "clv_label": self.clv_label(clv),
        }

    def save_record(self, record):
        try:
            df_new = pd.DataFrame([record])
            if CLV_FILE.exists():
                df_old = pd.read_csv(CLV_FILE)
                df = pd.concat([df_old, df_new], ignore_index=True)
            else:
                df = df_new
            df.to_csv(CLV_FILE, index=False)
            print(f"✅ ADVANCED CLV SAVED -> {CLV_FILE}")
        except Exception as e:
            print(f"❌ ADVANCED CLV SAVE ERROR: {e}")
