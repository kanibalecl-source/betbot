
class StageCMetaLayer:

    def enrich_pick(
        self,
        pick,
        market,
        model_prob,
        market_prob,
        xg_prob,
        momentum_prob,
        sharp_prob,
        base_stake,
        confidence,
        ev,
        risk_label,
        sharp_score=0,
        clv_percent=0,
        momentum_score=0
    ):

        try:

            model_prob = float(model_prob)
            market_prob = float(market_prob)
            xg_prob = float(xg_prob)
            momentum_prob = float(momentum_prob)
            sharp_prob = float(sharp_prob)

            if model_prob > 1:
                model_prob /= 100

            if market_prob > 1:
                market_prob /= 100

            if xg_prob > 1:
                xg_prob /= 100

            if momentum_prob > 1:
                momentum_prob /= 100

            if sharp_prob > 1:
                sharp_prob /= 100

            meta_weight_model = 0.30
            meta_weight_market = 0.20
            meta_weight_xg = 0.20
            meta_weight_momentum = 0.15
            meta_weight_sharp = 0.15

            if sharp_score >= 30:
                meta_weight_sharp += 0.10
                meta_weight_market += 0.05

            if momentum_score >= 70:
                meta_weight_momentum += 0.08

            total = (
                meta_weight_model
                + meta_weight_market
                + meta_weight_xg
                + meta_weight_momentum
                + meta_weight_sharp
            )

            meta_probability = (
                model_prob * meta_weight_model
                + market_prob * meta_weight_market
                + xg_prob * meta_weight_xg
                + momentum_prob * meta_weight_momentum
                + sharp_prob * meta_weight_sharp
            ) / total

            meta_probability = max(
                0.01,
                min(0.99, meta_probability)
            )

            dynamic_stake = base_stake

            if confidence >= 75:
                dynamic_stake *= 1.20

            if ev >= 8:
                dynamic_stake *= 1.15

            if sharp_score >= 30:
                dynamic_stake *= 1.15

            if risk_label == "HIGH":
                dynamic_stake *= 0.65

            dynamic_stake = round(dynamic_stake, 2)

            result = dict(pick)

            result.update({
                "meta_probability": round(meta_probability * 100, 2),
                "meta_weight_model": round(meta_weight_model, 2),
                "meta_weight_market": round(meta_weight_market, 2),
                "meta_weight_xg": round(meta_weight_xg, 2),
                "meta_weight_momentum": round(meta_weight_momentum, 2),
                "meta_weight_sharp": round(meta_weight_sharp, 2),
                "dynamic_stake": dynamic_stake,
            })

            return result

        except Exception as e:

            print(f"STAGE C ERROR: {e}")

            return {
                "meta_probability": 0,
                "meta_weight_model": 0,
                "meta_weight_market": 0,
                "meta_weight_xg": 0,
                "meta_weight_momentum": 0,
                "meta_weight_sharp": 0,
                "dynamic_stake": 0,
            }
