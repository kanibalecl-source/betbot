import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
from config import ODDS_API_KEY, ALLOWED_LEAGUES

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
ODDS_HISTORY_FILE = DATA_DIR / "odds_history.csv"

def normalize_name(name: str) -> str:
    return " ".join(name.lower().replace("fc", "").replace("cf", "").replace("club", "").replace("afc", "").replace(".", "").replace("-", " ").split())

def fetch_odds_for_sport(sport_key: str):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={ODDS_API_KEY}&regions=eu,uk&markets=h2h,totals,btts&oddsFormat=decimal"
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.json()

def collect_odds_snapshot():
    rows = []
    snapshot_time = datetime.utcnow().isoformat()
    for league_name, sport_key in ALLOWED_LEAGUES.items():
        try:
            events = fetch_odds_for_sport(sport_key)
        except Exception:
            continue
        for event in events:
            home = event.get("home_team")
            away = event.get("away_team")
            bookmakers = event.get("bookmakers", [])
            if not home or not away or not bookmakers:
                continue
            match_key = f"{normalize_name(home)}__{normalize_name(away)}"
            for bookmaker in bookmakers:
                book_name = bookmaker.get("title", "unknown")
                for market in bookmaker.get("markets", []):
                    for outcome in market.get("outcomes", []):
                        rows.append({
                            "snapshot_time": snapshot_time,
                            "league": league_name,
                            "sport_key": sport_key,
                            "match_key": match_key,
                            "home": home,
                            "away": away,
                            "bookmaker": book_name,
                            "market_key": market.get("key"),
                            "outcome_name": outcome.get("name"),
                            "point": outcome.get("point"),
                            "price": outcome.get("price"),
                        })
    if not rows:
        return pd.DataFrame()
    df_new = pd.DataFrame(rows)
    if ODDS_HISTORY_FILE.exists():
        df_old = pd.read_csv(ODDS_HISTORY_FILE)
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new
    df.to_csv(ODDS_HISTORY_FILE, index=False)
    print(f"Saved odds snapshot: {len(df_new)} rows")
    return df_new
