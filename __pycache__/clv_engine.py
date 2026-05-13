from datetime import datetime


class CLVEngine:

    def calculate_clv(
        self,
        odds_taken,
        closing_odds
    ):

        try:

            odds_taken = float(odds_taken)
            closing_odds = float(closing_odds)

            if odds_taken <= 0:
                return 0

            clv_percent = (
                (odds_taken / closing_odds) - 1
            ) * 100

            return round(clv_percent, 2)

        except Exception as e:

            print(f"CLV ENGINE ERROR: {e}")

            return 0


    def clv_status(
        self,
        clv_percent
    ):

        try:

            clv_percent = float(clv_percent)

            if clv_percent > 3:
                return "POSITIVE_CLV"

            if clv_percent < -3:
                return "NEGATIVE_CLV"

            return "NEUTRAL_CLV"

        except:

            return "UNKNOWN_CLV"


    def create_clv_record(
        self,
        match,
        market,
        pick,
        odds_taken,
        closing_odds,
        bookmaker=None
    ):

        clv = self.calculate_clv(
            odds_taken,
            closing_odds
        )

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "match": match,
            "market": market,
            "pick": pick,
            "bookmaker": bookmaker or "",
            "odds_taken": odds_taken,
            "closing_odds": closing_odds,
            "clv_percent": clv,
            "clv_status": self.clv_status(clv)
        }
