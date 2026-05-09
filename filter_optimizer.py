class FilterOptimizer:

    def should_accept_pick(
        self,
        confidence,
        ev,
        min_confidence=65,
        min_ev=5,
        league_allowed=True,
        market_allowed=True,
        tempo_level=None
    ):

        try:
            confidence = float(confidence)
            ev = float(ev)

            if confidence <= 1:
                confidence *= 100

            if confidence < min_confidence:
                return {
                    "accepted": False,
                    "reason": "LOW_CONFIDENCE"
                }

            if ev < min_ev:
                return {
                    "accepted": False,
                    "reason": "LOW_EV"
                }

            if not league_allowed:
                return {
                    "accepted": False,
                    "reason": "LEAGUE_BLOCKED"
                }

            if not market_allowed:
                return {
                    "accepted": False,
                    "reason": "MARKET_BLOCKED"
                }

            if tempo_level is not None and str(tempo_level).upper() == "LOW":
                return {
                    "accepted": False,
                    "reason": "LOW_TEMPO"
                }

            return {
                "accepted": True,
                "reason": "ACCEPTED"
            }

        except Exception as e:

            print(f"FILTER OPTIMIZER ERROR: {e}")

            return {
                "accepted": False,
                "reason": "FILTER_ERROR"
            }
