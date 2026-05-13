
class StageBModelLayer:

    def enrich_pick(
        self,
        pick,
        probability,
        home_xg,
        away_xg,
        minute=0,
        shots_on_target=0,
        dangerous_attacks=0,
        possession=50,
        pressure=50,
        corners=0,
        sharp_score=0,
        clv_score=0
    ):

        try:

            total_xg = float(home_xg) + float(away_xg)

            over25_prob = min(
                97,
                max(
                    3,
                    (total_xg / 3.0) * 100
                )
            )

            momentum_score = (
                shots_on_target * 4
                + dangerous_attacks * 0.8
                + pressure * 0.5
                + corners * 2
                + sharp_score * 0.6
                + clv_score * 0.4
            )

            if momentum_score >= 90:
                momentum_label = "EXTREME"
            elif momentum_score >= 70:
                momentum_label = "HIGH"
            elif momentum_score >= 45:
                momentum_label = "MEDIUM"
            else:
                momentum_label = "LOW"

            calibrated_conf = probability

            if probability <= 1:
                calibrated_conf = probability * 100

            calibrated_conf += sharp_score * 0.08
            calibrated_conf += (total_xg - 2.4) * 4
            calibrated_conf += clv_score * 0.05

            calibrated_conf = max(
                1,
                min(99, calibrated_conf)
            )

            result = dict(pick)

            result.update({
                "advanced_total_xg": round(total_xg, 2),
                "advanced_over25_prob": round(over25_prob, 2),
                "momentum_score": round(momentum_score, 2),
                "momentum_label": momentum_label,
                "confidence_calibrated_v2": round(calibrated_conf, 2),
            })

            return result

        except Exception as e:

            print(f"STAGE B ERROR: {e}")

            return {
                "advanced_total_xg": 0,
                "advanced_over25_prob": 0,
                "momentum_score": 0,
                "momentum_label": "ERROR",
                "confidence_calibrated_v2": 0,
            }
