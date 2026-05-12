
from connectors.oddsapi_connector import OddsAPIConnector
from engines.market_comparison_engine import MarketComparisonEngine

class RocketV9Orchestrator:
    def __init__(self):
        self.oddsapi = OddsAPIConnector()
        self.market = MarketComparisonEngine()

    def run(self):
        odds_data = self.oddsapi.get_soccer_odds()

        output = []

        for match in odds_data[:10]:
            fake_model_probability = 0.61
            best_odds = 1.90

            result = self.market.compare(
                fake_model_probability,
                best_odds
            )

            output.append({
                "match": match.get("home_team"),
                "analysis": result
            })

        return output

if __name__ == "__main__":
    bot = RocketV9Orchestrator()
    print(bot.run())
