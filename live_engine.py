import time
import requests
import pandas as pd
from pathlib import Path

from config import API_FOOTBALL_KEY

print("✅ LIVE_ENGINE IMPORT OK")

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


def analyze_match(match):
    minute = match["minute"]

    if minute >= 70:
        typ = "OVER 2.5"
        confidence = 82

    elif minute >= 55:
        typ = "BTTS"
        confidence = 76

    else:
        typ = "OVER 1.5"
        confidence = 65

    return {
        "mecz": match["mecz"],
        "liga": match["liga"],
        "minute": minute,
        "typ": typ,
        "confidence": confidence,
    }


def save_live_picks(picks):
    if not picks:
        return

    df = pd.DataFrame(picks)

    if CSV_FILE.exists():
        old = pd.read_csv(CSV_FILE)
        df = pd.concat([old, df], ignore_index=True)

    df.to_csv(CSV_FILE, index=False)

    print(f"✅ LIVE PICKS SAVED: {len(picks)}")


def run_live():
    print("⚽ LIVE ENGINE RUN")

    matches = get_live_matches()

    print(f"📡 LIVE MATCHES: {len(matches)}")

    picks = []

    for match in matches[:10]:
        result = analyze_match(match)

        print(
            f"🔥 {result['mecz']} | "
            f"{result['typ']} | "
            f"{result['confidence']}%"
        )

        picks.append(result)

    save_live_picks(picks)

    print("✅ LIVE ENGINE COMPLETE")
