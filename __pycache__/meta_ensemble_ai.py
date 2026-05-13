class MetaEnsembleAI:
    def dynamic_weights(self, market="", league_profile_strength=1.0, sharp_score=0, momentum_score=0, clv_percent=0):
        weights = {"model": 0.35, "market": 0.25, "xg": 0.20, "momentum": 0.10, "sharp": 0.10}
        try:
            sharp_score = float(sharp_score or 0)
            momentum_score = float(momentum_score or 0)
            clv_percent = float(clv_percent or 0)

            if sharp_score >= 30:
                weights["sharp"] += 0.10
                weights["market"] += 0.05
                weights["model"] -= 0.10
                weights["momentum"] -= 0.05

            if momentum_score >= 70:
                weights["momentum"] += 0.10
                weights["xg"] += 0.05
                weights["market"] -= 0.05
                weights["model"] -= 0.10

            if clv_percent > 3:
                weights["sharp"] += 0.05
                weights["market"] += 0.05
                weights["model"] -= 0.05
                weights["momentum"] -= 0.05

            market = str(market or "").upper()
            if "OVER" in market or "BTTS" in market:
                weights["xg"] += 0.05
                weights["momentum"] += 0.05
                weights["market"] -= 0.05
                weights["model"] -= 0.05

            total = sum(weights.values())
            return {k: round(v / total, 4) for k, v in weights.items()}
        except Exception:
            return weights

    def combine(self, model_prob=None, market_prob=None, xg_prob=None, momentum_prob=None, sharp_prob=None, weights=None):
        try:
            values = {"model": model_prob, "market": market_prob, "xg": xg_prob, "momentum": momentum_prob, "sharp": sharp_prob}
            if not weights:
                weights = self.dynamic_weights()
            total_weight = 0
            result = 0
            for key, value in values.items():
                if value is None:
                    continue
                p = float(value)
                if p > 1:
                    p = p / 100
                result += p * weights.get(key, 0)
                total_weight += weights.get(key, 0)
            if total_weight <= 0:
                return 0.50
            return round(max(0.03, min(0.97, result / total_weight)), 4)
        except Exception:
            return 0.50
