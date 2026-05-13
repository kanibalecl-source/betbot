
class MarketValueEngine:

    def calculate_ev(
        self,
        model_probability,
        bookmaker_odds
    ):

        try:

            model_probability = float(model_probability)

            if model_probability > 1:
                model_probability = model_probability / 100

            bookmaker_odds = float(bookmaker_odds)

            ev = (
                (model_probability * bookmaker_odds) - 1
            ) * 100

            return round(ev, 2)

        except:
            return 0


    def value_detected(
        self,
        ev,
        threshold=5
    ):

        try:

            ev = float(ev)

            return ev >= threshold

        except:
            return False
