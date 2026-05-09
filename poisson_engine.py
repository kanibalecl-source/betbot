import math


class PoissonEngine:

    def poisson_probability(self, lamb, goals):

        try:
            lamb = float(lamb)
            goals = int(goals)

            return (math.exp(-lamb) * (lamb ** goals)) / math.factorial(goals)

        except:
            return 0


    def over_probability(self, home_xg, away_xg, line=2.5, max_goals=10):

        try:
            total_xg = float(home_xg) + float(away_xg)
            prob_under = 0

            for goals in range(0, int(line) + 1):
                prob_under += self.poisson_probability(total_xg, goals)

            return round(1 - prob_under, 4)

        except:
            return 0.50


    def btts_probability(self, home_xg, away_xg):

        try:
            home_blank = self.poisson_probability(float(home_xg), 0)
            away_blank = self.poisson_probability(float(away_xg), 0)
            both_blank = home_blank * away_blank

            btts = 1 - home_blank - away_blank + both_blank

            return round(btts, 4)

        except:
            return 0.50
