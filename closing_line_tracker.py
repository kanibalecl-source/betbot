from pathlib import Path
import pandas as pd
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

CLV_FILE = DATA_DIR / "clv_history.csv"


class ClosingLineTracker:

    def save_record(
        self,
        record
    ):

        try:

            df_new = pd.DataFrame([record])

            if CLV_FILE.exists():
                df_old = pd.read_csv(CLV_FILE)
                df = pd.concat(
                    [df_old, df_new],
                    ignore_index=True
                )

            else:
                df = df_new

            df.to_csv(
                CLV_FILE,
                index=False
            )

            print(f"✅ CLV RECORD SAVED -> {CLV_FILE}")

        except Exception as e:

            print(f"❌ CLV SAVE ERROR: {e}")


    def load_history(
        self
    ):

        try:

            if not CLV_FILE.exists():
                return pd.DataFrame()

            return pd.read_csv(CLV_FILE)

        except Exception as e:

            print(f"❌ CLV LOAD ERROR: {e}")

            return pd.DataFrame()
