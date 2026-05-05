import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
LEAGUE_FILE = DATA_DIR / "league_performance.csv"


def update_league_performance(bet):
    row = {
        "league": bet["league"],
        "edge": bet["true_edge"],
        "result": bet.get("result", 0)  # 1 win, 0 lose
    }

    df = pd.DataFrame([row])

    if LEAGUE_FILE.exists():
        old = pd.read_csv(LEAGUE_FILE)
        df = pd.concat([old, df], ignore_index=True)

    df.to_csv(LEAGUE_FILE, index=False)


def get_league_scores():
    if not LEAGUE_FILE.exists():
        return {}

    df = pd.read_csv(LEAGUE_FILE)

    grouped = df.groupby("league").agg({
        "result": "mean",
        "edge": "mean"
    }).reset_index()

    grouped["score"] = grouped["result"] * 0.7 + grouped["edge"] * 0.3

    scores = dict(zip(grouped["league"], grouped["score"]))

    return scores


def is_league_good(league, threshold=0.52):
    scores = get_league_scores()

    if league not in scores:
        return True  # nowe ligi testujemy

    return scores[league] >= threshold