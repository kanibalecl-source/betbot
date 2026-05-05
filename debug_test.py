import requests
from config import API_FOOTBALL_KEY
from data_api import get_matches, get_odds_from_snapshots

print("=== TEST START ===\n")

# 🔥 1. TEST API
print("1. TEST API...")
url = "https://v3.football.api-sports.io/fixtures?next=5"
headers = {"x-apisports-key": API_FOOTBALL_KEY}

try:
    r = requests.get(url, headers=headers, timeout=10)
    print("STATUS:", r.status_code)
except Exception as e:
    print("API ERROR:", e)

print("\n------------------\n")

# 🔥 2. TEST MATCHES
print("2. TEST MATCHES...")
try:
    matches = get_matches()
    print("MATCHES COUNT:", len(matches))

    if len(matches) > 0:
        print("SAMPLE MATCH:", matches[0]["match"])
except Exception as e:
    print("MATCH ERROR:", e)

print("\n------------------\n")

# 🔥 3. TEST ODDS
print("3. TEST ODDS...")
try:
    if len(matches) > 0:
        for m in matches[:3]:
            odds = get_odds_from_snapshots(m["match_key"])
            print(m["match"], "ODDS:", odds["home_win"]["current"])
except Exception as e:
    print("ODDS ERROR:", e)

print("\n=== TEST END ===")