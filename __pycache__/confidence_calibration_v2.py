class ConfidenceCalibrationV2:
    def calibrate(self, probability, sample_size=100, model_reliability=0.65, sharp_score=0, clv_score=0):
        try:
            p = float(probability)
            if p > 1:
                p = p / 100
            sample_size = max(float(sample_size or 0), 1)
            shrink_strength = min(0.30, 30 / sample_size)
            calibrated = (p * (1 - shrink_strength)) + (0.50 * shrink_strength)
            calibrated = (calibrated * model_reliability) + (p * (1 - model_reliability))
            calibrated += float(sharp_score or 0) * 0.0005
            calibrated += float(clv_score or 0) * 0.0008
            return round(max(0.03, min(0.97, calibrated)), 4)
        except Exception:
            return 0.50
