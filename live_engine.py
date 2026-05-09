from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

LIVE_FILE = DATA_DIR / "live_matches.csv"


class LiveEngine:
    def __init__(self):
        pass

    def save_live_matches(self, matches):

        try:

            if not matches:
                print("⚠️ NO LIVE MATCHES")
                return

            cleaned_matches = []

            for match in matches:

                cleaned_matches.append({

                    "home": match.get("home", ""),
                    "away": match.get("away", ""),
                    "league": match.get("league", ""),
                    "minute": match.get("minute", ""),
                    "score": match.get("score", ""),
                    "signal": match.get("signal", ""),
                    "confidence": match.get("confidence", 0),
                    "ev": match.get("ev", 0),
                    "status": match.get("status", "LIVE"),
                    "risk": match.get("risk", "LOW")

                })

            df = pd.DataFrame(cleaned_matches)

            df.to_csv(
                LIVE_FILE,
                index=False
            )

            print(f"✅ LIVE SAVED -> {LIVE_FILE}")
            print(f"✅ MATCHES COUNT -> {len(df)}")

        except Exception as e:
            print(f"❌ SAVE LIVE ERROR: {e}")

    def load_live_matches(self):

        try:

            if not LIVE_FILE.exists():
                return []

            df = pd.read_csv(LIVE_FILE)
            df = df.fillna("")

            return df.to_dict(orient="records")

        except Exception as e:
            print(f"❌ LOAD LIVE ERROR: {e}")
            return []
