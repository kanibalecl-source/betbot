import requests
import pandas as pd
from config import API_FOOTBALL_KEY
from cashout_engine import cashout_signal
from telegram_notifier import send_telegram

HEADERS = {
    "x-apisports-key": API_FOOTBALL_KEY
}


def get_live_matches():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    res = requests.get(url, headers=HEADERS, timeout=20)
    res.raise_for_status()

    data = res.json().get("response", [])

    matches = []

    for m in data:
        matches.append({
            "fixture_id": m["fixture"]["id"],
            "match": f"{m['teams']['home']['name']} vs {m['teams']['away']['name']}",
            "league": m["league"]["name"],
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
            "match": m["match"],
            "odds_taken": 2.20,
        } for m in matches
    ]

    results = []

    for m in matches:

        live_odds = get_live_odds(m["fixture_id"])

        if not live_odds:
            continue

        pressure_home = 50
        pressure_away = 40

        for bet in active_bets:
            if bet["match"] == m["match"]:

                signal = cashout_signal(
                    bet=bet,
                    live_odds=live_odds,
                    minute=m["minute"],
                    pressure_home=pressure_home,
                    pressure_away=pressure_away,
                )

                msg = f"{m['match']} ({m['minute']} min)\nOdds: {live_odds}\n→ {signal}"

                print(msg)

                # 🔥 WYŚLIJ NA TELEGRAM
                if "CASHOUT" in signal:
                    send_telegram(msg)

                results.append({
                    "match": m["match"],
                    "minute": m["minute"],
                    "live_odds": live_odds,
                    "signal": signal
                })

    return pd.DataFrame(results)