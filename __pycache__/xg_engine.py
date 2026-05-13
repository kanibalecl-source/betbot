
import math

class XGEngine:

    def weighted_xg(
        self,
        xg_for,
        xg_against,
        recent_form=1,
        home_advantage=1
    ):

        try:

            xg_for = float(xg_for)
            xg_against = float(xg_against)
            recent_form = float(recent_form)
            home_advantage = float(home_advantage)

            attack_strength = (
                xg_for * 0.65
            ) * recent_form

            defense_weakness = (
                xg_against * 0.35
            )

            final_xg = (
                attack_strength +
                defense_weakness
            ) * home_advantage

            return round(final_xg, 2)

        except Exception as e:

            print(f"XG ENGINE ERROR: {e}")

            return 0


    def fair_odds(
        self,
        probability
    ):

        try:

            probability = float(probability)

            if probability <= 0:
                return 999

            if probability > 1:
                probability = probability / 100

            return round(
                1 / probability,
                2
            )

        except:
            return 999


    def calculate_probability(
        self,
        home_xg,
        away_xg
    ):

        try:

            total = float(home_xg) + float(away_xg)

            if total <= 0:
                return 0.5

            probability = (
                float(home_xg) / total
            )

            return round(probability, 4)

        except:
            return 0.5
