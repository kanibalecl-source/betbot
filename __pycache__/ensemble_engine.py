class EnsembleEngine:

    def combine_probabilities(
        self,
        poisson_probability=None,
        xg_probability=None,
        elo_probability=None,
        market_probability=None,
        ml_probability=None
    ):

        inputs = {
            "poisson": poisson_probability,
            "xg": xg_probability,
            "elo": elo_probability,
            "market": market_probability,
            "ml": ml_probability
        }

        weights = {
            "poisson": 0.25,
            "xg": 0.30,
            "elo": 0.15,
            "market": 0.20,
            "ml": 0.10
        }

        total_weight = 0
        weighted_sum = 0

        for key, value in inputs.items():

            if value is None:
                continue

            try:
                p = float(value)

                if p > 1:
                    p = p / 100

                weighted_sum += p * weights[key]
                total_weight += weights[key]

            except:
                continue

        if total_weight <= 0:
            return 0.50

        final_probability = weighted_sum / total_weight

        if final_probability < 0.03:
            final_probability = 0.03

        if final_probability > 0.97:
            final_probability = 0.97

        return round(final_probability, 4)


    def fair_odds(self, probability):

        try:
            p = float(probability)

            if p <= 0:
                return 999

            if p > 1:
                p = p / 100

            return round(1 / p, 2)

        except:
            return 999
