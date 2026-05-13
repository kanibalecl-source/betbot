from sharp_money_detector import SharpMoneyDetector
from league_profile_engine import LeagueProfileEngine

class StageAValueLayer:
    def __init__(self):
        self.sharp = SharpMoneyDetector()
        self.league_profiles = LeagueProfileEngine()

    def enrich_pick(self, pick, probability, league, market, opening_odds=None, current_odds=None, market_avg_odds=None, pinnacle_odds=None, betfair_odds=None):
        sharp_data = self.sharp.detect(
            opening_odds=opening_odds,
            current_odds=current_odds,
            market_avg_odds=market_avg_odds,
            pinnacle_odds=pinnacle_odds,
            betfair_odds=betfair_odds,
        )

        adjusted_probability = self.league_profiles.adjust_probability(
            probability=probability,
            league_name=league,
            market=market,
        )

        result = dict(pick)
        result.update({
            "stage_a_probability": adjusted_probability,
            "sharp_score": sharp_data["sharp_score"],
            "sharp_label": sharp_data["sharp_label"],
            "sharp_signals": sharp_data["sharp_signals"],
            "league_profile_active": "YES",
        })
        return result
