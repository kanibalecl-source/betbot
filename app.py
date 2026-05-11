from pathlib import Path
import os
import pandas as pd
from flask import Flask, render_template, request, jsonify, redirect, url_for

from database import init_db, save_bet, list_bets

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

PICKS_FILE = DATA_DIR / "live_matches.csv"

app = Flask(__name__)


def load_picks():
    if not PICKS_FILE.exists():
        return []

    try:
        df = pd.read_csv(PICKS_FILE)
        df = df.fillna("")
        return df.to_dict(orient="records")

    except Exception as e:
        print(f"LOAD PICKS ERROR: {e}")
        return []


@app.route("/")
def index():
    init_db()

    picks = load_picks()

    return render_template(
        "index.html",
        picks=picks,
        page="dashboard"
    )


@app.route("/bets")
def bets():
    init_db()

    rows = list_bets(1000)

    return render_template(
        "bets.html",
        bets=rows,
        page="bets"
    )


@app.post("/play")
def play():
    picks = load_picks()

    pick_id = request.form.get("pick_id")
    stake = request.form.get("stake")

    if not pick_id or not stake:
        return jsonify({
            "ok": False,
            "error": "Brak pick_id albo stawki"
        }), 400

    pick = next(
        (
            p for p in picks
            if str(p.get("pick_id")) == str(pick_id)
        ),
        None,
    )

    if not pick:
        return jsonify({
            "ok": False,
            "error": "Nie znaleziono typu"
        }), 404

    save_bet(pick, stake)

    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
