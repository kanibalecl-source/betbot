from pathlib import Path
import pandas as pd

try:
    from prediction_pipeline_integration import process_and_save_matches
except Exception:
    process_and_save_matches = None

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

LIVE_FILE = DATA_DIR / "live_matches.csv"


FINISHED_STATUSES = [
    "FT",
    "FINISHED",
    "ENDED",
    "AFTER PEN.",
    "AFTER PENALTIES",
    "FULLTIME",
    "AET"
]


def is_live_match(match):
    try:
        status = str(match.get("status", "")).upper()

        if status in FINISHED_STATUSES:
            return False

        minute = match.get("minute", 0)

        try:
            minute = int(minute)
        except:
            minute = 0

        if minute >= 120:
            return False

        return True

    except:
        return False


class LiveEngine:
    def __init__(self):
        pass

    def save_live_matches(self, matches):

        try:
            if not matches:
                print("⚠️ NO LIVE MATCHES")
                return

            active_matches = [
                match for match in matches
                if is_live_match(match)
            ]

            print(f"✅ ACTIVE LIVE MATCHES -> {len(active_matches)}")

            if process_and_save_matches:
                process_and_save_matches(active_matches)
                return

            cleaned_matches = []

            for match in active_matches:
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
            df.to_csv(LIVE_FILE, index=False)

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
