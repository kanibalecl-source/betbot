
import math

class TempoEngine:

    def calculate_tempo(
        self,
        shots_on_target=0,
        dangerous_attacks=0,
        possession=50,
        pressure=0,
        xg_live=0
    ):

        try:

            tempo_score = (
                (float(shots_on_target) * 0.30) +
                (float(dangerous_attacks) * 0.25) +
                (float(possession) * 0.10) +
                (float(pressure) * 0.20) +
                (float(xg_live) * 15)
            )

            if tempo_score >= 75:
                level = "HIGH"

            elif tempo_score >= 45:
                level = "MEDIUM"

            else:
                level = "LOW"

            return {
                "tempo_score": round(tempo_score, 2),
                "tempo_level": level
            }

        except Exception as e:

            print(f"TEMPO ENGINE ERROR: {e}")

            return {
                "tempo_score": 0,
                "tempo_level": "LOW"
            }
