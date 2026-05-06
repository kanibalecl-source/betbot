import time
import requests
import pandas as pd
from pathlib import Path

from config import API_FOOTBALL_KEY
from cashout_engine import cashout_signal
from telegram_notifier import send_telegram

HEADERS = {
    "x-apisports-key": API_FOOTBALL_KEY
}

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CSV_FILE = DATA_DIR / "auto_all_picks.csv"


def get_live_matches():
    url = "https://v3.football.api-sports.io/fixtures?live=all"

    res = requests.get(url, headers=HEADERS, timeout=20)
    res.raise_for_status()

    data = res.json().get("response", [])

    matches = []

    for m in data:
        matches.append({
            "fixture_id": m["fixture"]["id"],
            "mecz": f"{m['teams']['home']['name']} vs {m['teams']['away']['name']}",
            "liga": m["league"]["name"],
            "minute": m["fixture"]["status"]["elapsed"] or 0,
        })

    return matches


def get_live_odds(fixture_id):
    url = f"https://v3.football.api-sports.io/odds?fixture={fixture_id}"

    res = requests.get(url, headers=HEADERS, timeout=20)

    if res.status_code != 200:
        return None

    data = res.json().get("response", [])

    try:
        bookmakers = data[0]["bookmakers"]

        for b in bookmakers:
            for bet in b["bets"]:
                if bet["name"] == "Match Winner":

                    for outcome in bet["values"]:
                        if outcome["value"] == "Home":
                            return float(outcome["odd"])

    except:
        return None

    return None


def scan_live():

    matches = get_live_matches()

    active_bets = [
        {
            "mecz": m["mecz"],
            "odds_taken": 2.20,
        }
        for m in matches
    ]

    results = []

    for m in matches:

        live_odds = get_live_odds(m["fixture_id"])

        if not live_odds:
            continue

        pressure_home = 50
        pressure_away = 40

        for bet in active_bets:

            if bet["mecz"] == m["mecz"]:

                signal = cashout_signal(
                    bet=bet,
                    live_odds=live_odds,
                    minute=m["minute"],
                    pressure_home=pressure_home,
                    pressure_away=pressure_away,
                )

                msg = (
                    f"{m['mecz']} ({m['minute']} min)\n"
                    f"Odds: {live_odds}\n"
                    f"→ {signal}"
                )

                print(msg)

                if "CASHOUT" in signal:
                    try:
                        send_telegram(msg)
                    except Exception as e:
                        print("TELEGRAM ERROR:", e)

                results.append({
                    "data_analizy": pd.Timestamp.now(),
                    "liga": m["liga"],
                    "mecz": m["mecz"],
                    "typ": signal,
                    "kod_rynku": "LIVE",
                    "kurs_buk": live_odds,
                    "prawd_bota": 0,
                    "kurs_bota": 0,
                    "edge": 0,
                    "ocena": "LIVE",
                    "stawka_pln": 0,
                })

    return pd.DataFrame(results)


print("LIVE ENGINE START 🚀")

while True:

    try:

        df = scan_live()

        if not df.empty:
            df.to_csv(CSV_FILE, index=False)

            print(f"ZAPISANO {len(df)} LIVE PICKS")

        else:
            print("BRAK LIVE PICKS")

    except Exception as e:

        print("LIVE ENGINE ERROR:", e)

    time.sleep(60)
