class DynamicBankrollAI:
    def stake_multiplier(self, confidence=0, ev=0, risk_label="MEDIUM", sharp_score=0, clv_percent=0, drawdown_percent=0):
        try:
            confidence = float(confidence)
            ev = float(ev)
            sharp_score = float(sharp_score or 0)
            clv_percent = float(clv_percent or 0)
            drawdown_percent = float(drawdown_percent or 0)

            if confidence <= 1:
                confidence *= 100

            multiplier = 1.00
            if confidence >= 75:
                multiplier += 0.20
            if ev >= 8:
                multiplier += 0.15
            if sharp_score >= 30:
                multiplier += 0.15
            if clv_percent >= 3:
                multiplier += 0.10

            risk_label = str(risk_label or "").upper()
            if risk_label == "HIGH":
                multiplier -= 0.30
            elif risk_label == "MEDIUM":
                multiplier -= 0.10

            if drawdown_percent <= -10:
                multiplier -= 0.40

            return round(max(0.25, min(1.50, multiplier)), 3)
        except Exception:
            return 1.00

    def adjusted_stake(self, base_stake, **kwargs):
        try:
            return round(float(base_stake) * self.stake_multiplier(**kwargs), 2)
        except Exception:
            return 0
