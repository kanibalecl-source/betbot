import os
from dotenv import load_dotenv

# wczytaj zmienne środowiskowe
load_dotenv()

# 🔑 API (NOWE - potrzebne do działania bota)
API_FOOTBALL_KEY = os.getenv("0d7ba25228cd257230eb64bc1ed3ed3f")
TELEGRAM_TOKEN = os.getenv("8770844047:AAFPkni-UjEIXqHfXJ_sg97pUZhVBGdwDh0")
CHAT_ID = os.getenv("8770844047")


# =========================
# 💰 TWOJE USTAWIENIA (BEZ ZMIAN)
# =========================

BANKROLL = 1000.0

MAX_TOTAL_PICKS = 12
MAX_PICKS_PER_MATCH = 2
MAX_PICKS_PER_LEAGUE = 3

ALLOW_RISK_IN_DASHBOARD = True

SAFE_MIN_EDGE = 0.07
LOW_MIN_EDGE = 0.02

SAFE_MIN_ODDS = 1.20
SAFE_MAX_ODDS = 3.50
LOW_MAX_ODDS = 5.00

MIN_BOOKS_FOR_SAFE = 2
MIN_BOOKS_FOR_LOW = 2


# 🔍 DEBUG (opcjonalnie - tylko informacja w logach)
if not API_FOOTBALL_KEY:
    print("❌ Brak API_FOOTBALL_KEY")

if not TELEGRAM_TOKEN:
    print("❌ Brak TELEGRAM_TOKEN")

if not CHAT_ID:
    print("❌ Brak CHAT_ID")
