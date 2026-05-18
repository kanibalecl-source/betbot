import os
import csv
import random
from datetime import datetime

AI_OUTPUT = "data/ai_picks.csv"

def bootstrap_ai_picks():
    os.makedirs("data", exist_ok=True)

    rows = [
        ["league","match","market","odds","confidence","edge","status"],
        ["Premier League","Arsenal vs Chelsea","OVER_2_5","1.92","74","0.14","AI VALUE"],
        ["La Liga","Real Madrid vs Sevilla","BTTS_YES","1.78","71","0.11","AI VALUE"],
        ["Serie A","Inter vs Milan","HOME_WIN","1.66","77","0.18","AI STRONG"],
    ]

    with open(AI_OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    print("[AI] bootstrap ai_picks.csv generated")

if __name__ == "__main__":
    bootstrap_ai_picks()
