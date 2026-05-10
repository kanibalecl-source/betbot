from advanced_xg_engine import AdvancedXGEngine
from live_momentum_engine import LiveMomentumEngine
from confidence_calibration_v2 import ConfidenceCalibrationV2


class StageBModelLayer:
    def __init__(self):
        self.xg = AdvancedXGEngine()
        self.momentum = LiveMomentumEngine()
        self.calibration = ConfidenceCalibrationV2()

    def enrich_pick(self, pick, probability, home_xg=1.2, away_xg=1.2, minute=0, shots_on_target=0, dangerous_attacks=0, possession=50, pressure=50, corners=0, sharp_score=0, clv_score=0):
        total_xg = self.xg.match_total_xg(home_xg, away_xg)
        over_25_probability = self.xg.over_probability_from_xg(total_xg=total_xg, line=2.5)
        momentum_data = self.momentum.calculate_momentum(
            minute=minute,
            shots_on_target=shots_on_target,
            dangerous_attacks=dangerous_attacks,
            possession=possession,
            pressure=pressure,
            corners=corners,
        )
        calibrated = self.calibration.calibrate(probability=probability, sharp_score=sharp_score, clv_score=clv_score)
        result = dict(pick)
        result.update({
            "advanced_total_xg": total_xg,
            "advanced_over25_prob": over_25_probability,
            "momentum_score": momentum_data["momentum_score"],
            "momentum_label": momentum_data["momentum_label"],
            "confidence_calibrated_v2": calibrated,
        })
        return result
