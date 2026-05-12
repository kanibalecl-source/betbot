
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4/sports"

class OddsAPIConnector:
    def __init__(self):
        self.api_key = API_KEY

    def get_soccer_odds(self):
        sports = [
            "soccer_epl",
            "soccer_spain_la_liga",
            "soccer_italy_serie_a",
            "soccer_germany_bundesliga",
            "soccer_france_ligue_one"
        ]

        all_matches = []

        for sport in sports:
            url = f"{BASE_URL}/{sport}/odds"

            params = {
                "apiKey": self.api_key,
                "regions": "eu",
                "markets": "h2h,totals,btts",
                "oddsFormat": "decimal",
                "dateFormat": "iso"
            }

            try:
                response = requests.get(url, params=params, timeout=30)

                if response.status_code == 200:
                    all_matches.extend(response.json())

            except Exception as e:
                print(f"ODDS API ERROR: {e}")

        return all_matches
