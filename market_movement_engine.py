class MarketMovementEngine:

    def calculate_movement(
        self,
        opening_odds,
        current_odds
    ):

        try:

            opening_odds = float(opening_odds)
            current_odds = float(current_odds)

            if opening_odds <= 0:
                return {
                    "movement_percent": 0,
                    "direction": "UNKNOWN",
                    "signal": "NO_SIGNAL"
                }

            movement_percent = (
                (current_odds - opening_odds) / opening_odds
            ) * 100

            if movement_percent <= -5:
                direction = "STEAM_DOWN"
                signal = "MARKET_BACKING"

            elif movement_percent >= 5:
                direction = "DRIFT_UP"
                signal = "MARKET_REJECTING"

            else:
                direction = "STABLE"
                signal = "NO_SIGNAL"

            return {
                "movement_percent": round(movement_percent, 2),
                "direction": direction,
                "signal": signal
            }

        except Exception as e:

            print(f"MARKET MOVEMENT ERROR: {e}")

            return {
                "movement_percent": 0,
                "direction": "UNKNOWN",
                "signal": "NO_SIGNAL"
            }


    def market_boost(
        self,
        opening_odds,
        current_odds
    ):

        movement = self.calculate_movement(
            opening_odds,
            current_odds
        )

        direction = movement.get("direction")

        if direction == "STEAM_DOWN":
            return 0.04

        if direction == "DRIFT_UP":
            return -0.03

        return 0
