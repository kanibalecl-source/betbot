
class ConfidenceCalibration:

    def calibrate(self, raw_probability):

        try:

            raw_probability = float(raw_probability)

            if raw_probability > 1:
                raw_probability = raw_probability / 100

            calibrated = (
                raw_probability * 0.92
            ) + 0.04

            return round(calibrated, 4)

        except:
            return 0.50
