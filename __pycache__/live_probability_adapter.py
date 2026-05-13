from bayesian_live_engine import BayesianLiveEngine


class LiveProbabilityAdapter:

    def build_live_probability(
        self,
        base_probability,
        tempo_score,
        pressure,
        momentum,
        score_state=0,
        red_card_for=False,
        red_card_against=False
    ):

        engine = BayesianLiveEngine()

        probability = engine.update_probability(
            prematch_probability=base_probability,
            tempo_score=tempo_score,
            pressure=pressure,
            momentum=momentum,
            red_card_for=red_card_for,
            red_card_against=red_card_against,
            score_state=score_state
        )

        fair_odds = engine.fair_odds(probability)

        return {
            "live_probability": probability,
            "live_probability_percent": round(probability * 100, 2),
            "live_fair_odds": fair_odds
        }
