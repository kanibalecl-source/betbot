class RiskManager:

    def risk_label(
        self,
        confidence,
        ev,
        tempo_level=None
    ):

        try:
            confidence = float(confidence)

            if confidence <= 1:
                confidence *= 100

            ev = float(ev)

            tempo = str(tempo_level or "").upper()

            if confidence >= 75 and ev >= 10 and tempo != "LOW":
                return "LOW"

            if confidence >= 65 and ev >= 5:
                return "MEDIUM"

            return "HIGH"

        except:
            return "HIGH"


    def allow_bet(
        self,
        risk,
        max_allowed="MEDIUM"
    ):

        order = {
            "LOW": 1,
            "MEDIUM": 2,
            "HIGH": 3
        }

        return order.get(str(risk).upper(), 3) <= order.get(str(max_allowed).upper(), 2)
