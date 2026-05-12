
def implied_probability(odds: float):
    return 1 / odds

class MarketComparisonEngine:
    def compare(self, model_probability, best_odds):
        market_probability = implied_probability(best_odds)

        edge = model_probability - market_probability
        ev = (model_probability * best_odds) - 1

        return {
            "model_probability": model_probability,
            "market_probability": market_probability,
            "edge": edge,
            "ev": ev
        }
