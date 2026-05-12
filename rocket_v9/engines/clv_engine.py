
from datetime import datetime

class CLVEngine:
    def build_snapshot(
        self,
        opening_odds,
        current_odds,
        closing_odds,
        bookmaker
    ):
        return {
            "opening_odds": opening_odds,
            "current_odds": current_odds,
            "closing_odds": closing_odds,
            "bookmaker": bookmaker,
            "timestamp": datetime.utcnow().isoformat()
        }
