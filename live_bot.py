import requests
import time
from model_goals import build_model

API_KEY = "TWOJ_KLUCZ"
BASE_URL = "https://v3.football.api-sports.io"

HEADERS = {"x-apisports-key": API_KEY}


def get_live_matches():
    r = requests.get(
        BASE_URL + "/fixtures",
        headers=HEADERS,
        params={"live": "all"}
    )
    return r.json().get("response", [])


def analyze_live(match):
    minute = match["fixture"]["status"]["elapsed"]
    home = match["goals"]["home"]
    away = match["goals"]["away"]

    total = home + away

    # 🔥 STRATEGIA OVER
    if minute > 60 and total <= 1:
        return "OVER 1.5 → WEJDŹ"

    if minute > 70 and total == 0:
        return "OVER 0.5 → AGRESYWNIE"

    return None


def run_live():
    print("=== LIVE BOT START ===")

    while True:
        matches = get_live_matches()

        for m in matches:
            signal = analyze_live(m)

            if signal:
                print(
                    m["teams"]["home"]["name"],
                    "vs",
                    m["teams"]["away"]["name"],
                    "|",
                    signal
                )

        time.sleep(60)