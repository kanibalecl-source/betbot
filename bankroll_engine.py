class BankrollEngine:

    def kelly_fraction(
        self,
        probability,
        odds
    ):

        try:
            p = float(probability)

            if p > 1:
                p = p / 100

            odds = float(odds)

            b = odds - 1
            q = 1 - p

            if b <= 0:
                return 0

            kelly = ((b * p) - q) / b

            if kelly < 0:
                kelly = 0

            return round(kelly, 4)

        except Exception as e:

            print(f"KELLY ERROR: {e}")

            return 0


    def recommended_stake(
        self,
        bankroll,
        probability,
        odds,
        fraction=0.25,
        max_percent=2.0
    ):

        try:
            bankroll = float(bankroll)

            kelly = self.kelly_fraction(
                probability,
                odds
            )

            stake = bankroll * kelly * float(fraction)

            max_stake = bankroll * (float(max_percent) / 100)

            if stake > max_stake:
                stake = max_stake

            return round(stake, 2)

        except Exception as e:

            print(f"STAKE ERROR: {e}")

            return 0
