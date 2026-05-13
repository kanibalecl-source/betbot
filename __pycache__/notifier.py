import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=20)
    except Exception:
        pass

def send_picks(df):
    if df is None or df.empty:
        send_telegram("NO BET DAY")
        return
    msg = "🔥 TOP PICKS\n\n"
    for _, row in df.iterrows():
        msg += f"{row['match']}\n{row['market']} @ {row['current_odds']}\nTrue Edge: {row['true_edge']}\nTiming: {row['timing']}\nOdds Quality: {row['odds_quality']}\nStake: {row['stake_units']}u\n\n"
    send_telegram(msg[:3900])

def send_live(df):
    if df is None or df.empty:
        return
    msg = "⚡ LIVE WATCHLIST\n\n"
    for _, row in df.iterrows():
        msg += f"{row['match']} ({int(row['minute'])}')\n{row['market']}\n{row['note']}\n\n"
    send_telegram(msg[:3900])
