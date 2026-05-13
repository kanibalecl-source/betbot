class LiveMomentumEngine:
    def calculate_momentum(self, minute=0, shots_on_target=0, dangerous_attacks=0, possession=50, pressure=50, corners=0, red_card_for=False, red_card_against=False, score_state=0):
        try:
            minute = float(minute or 0)
            shots_on_target = float(shots_on_target or 0)
            dangerous_attacks = float(dangerous_attacks or 0)
            possession = float(possession or 50)
            pressure = float(pressure or 50)
            corners = float(corners or 0)
            score_state = float(score_state or 0)

            score = 0
            score += shots_on_target * 8
            score += dangerous_attacks * 0.45
            score += (possession - 50) * 0.35
            score += (pressure - 50) * 0.55
            score += corners * 3
            score += score_state * 8

            if 20 <= minute <= 38:
                score += 5
            if 55 <= minute <= 78:
                score += 8
            if red_card_for:
                score -= 20
            if red_card_against:
                score += 20

            score = max(0, min(100, score))
            label = "HIGH_MOMENTUM" if score >= 75 else "MEDIUM_MOMENTUM" if score >= 45 else "LOW_MOMENTUM"
            return {"momentum_score": round(score, 2), "momentum_label": label}
        except Exception as e:
            print(f"LIVE MOMENTUM ERROR: {e}")
            return {"momentum_score": 0, "momentum_label": "LOW_MOMENTUM"}
