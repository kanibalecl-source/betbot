class SharpMoneyDetector:
    def detect(self, opening_odds=None, current_odds=None, market_avg_odds=None, pinnacle_odds=None, betfair_odds=None):
        try:
            current_odds = float(current_odds)
            signals = []
            score = 0

            if opening_odds:
                opening_odds = float(opening_odds)
                movement = ((current_odds - opening_odds) / opening_odds) * 100
                if movement <= -5:
                    signals.append("STEAM_DOWN")
                    score += 25
                elif movement >= 5:
                    signals.append("DRIFT_UP")
                    score -= 20

            if market_avg_odds:
                market_avg_odds = float(market_avg_odds)
                diff = ((market_avg_odds - current_odds) / market_avg_odds) * 100
                if diff >= 3:
                    signals.append("BOOK_BELOW_MARKET")
                    score += 15
                elif diff <= -3:
                    signals.append("BOOK_ABOVE_MARKET")
                    score -= 10

            if pinnacle_odds:
                pinnacle_odds = float(pinnacle_odds)
                if current_odds >= pinnacle_odds * 1.03:
                    signals.append("BETTER_THAN_SHARP")
                    score += 25
                elif current_odds <= pinnacle_odds * 0.97:
                    signals.append("WORSE_THAN_SHARP")
                    score -= 15

            if betfair_odds:
                betfair_odds = float(betfair_odds)
                if current_odds >= betfair_odds * 1.03:
                    signals.append("BETFAIR_VALUE")
                    score += 15

            if not signals:
                signals.append("NO_SHARP_SIGNAL")

            if score >= 40:
                label = "STRONG_SHARP_SUPPORT"
            elif score >= 15:
                label = "SHARP_SUPPORT"
            elif score <= -20:
                label = "MARKET_WARNING"
            else:
                label = "NEUTRAL"

            return {"sharp_score": round(score, 2), "sharp_label": label, "sharp_signals": "|".join(signals)}
        except Exception as e:
            print(f"SHARP MONEY DETECTOR ERROR: {e}")
            return {"sharp_score": 0, "sharp_label": "UNKNOWN", "sharp_signals": "ERROR"}
