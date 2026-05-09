class BayesianLiveEngine:

    def update_probability(
        self,
        prematch_probability,
        tempo_score=0,
        pressure=0,
        momentum=0,
        red_card_for=False,
        red_card_against=False,
        score_state=0
    ):

        try:
            p = float(prematch_probability)

            if p > 1:
                p = p / 100

            tempo_score = float(tempo_score)
            pressure = float(pressure)
            momentum = float(momentum)
            score_state = float(score_state)

            live_adjustment = 0

            live_adjustment += (tempo_score - 50) * 0.0015
            live_adjustment += (pressure - 50) * 0.0010
            live_adjustment += (momentum - 50) * 0.0012
            live_adjustment += score_state * 0.035

            if red_card_for:
                live_adjustment -= 0.08

            if red_card_against:
                live_adjustment += 0.08

            updated = p + live_adjustment

            if updated < 0.03:
                updated = 0.03

            if updated > 0.97:
                updated = 0.97

            return round(updated, 4)

        except Exception as e:
            print(f"BAYESIAN LIVE ERROR: {e}")
            return 0.50


    def fair_odds(self, probability):

        try:
            probability = float(probability)

            if probability <= 0:
                return 999

            if probability > 1:
                probability = probability / 100

            return round(1 / probability, 2)

        except:
            return 999
