DEFAULT_PROFILE = {"tempo_factor": 1.00, "over_factor": 1.00, "btts_factor": 1.00, "draw_factor": 1.00, "variance_factor": 1.00}

LEAGUE_PROFILES = {
    "Premier League": {"tempo_factor": 1.08, "over_factor": 1.04, "btts_factor": 1.03, "draw_factor": 0.96, "variance_factor": 1.00},
    "Bundesliga": {"tempo_factor": 1.12, "over_factor": 1.08, "btts_factor": 1.06, "draw_factor": 0.95, "variance_factor": 1.03},
    "Serie A": {"tempo_factor": 0.96, "over_factor": 0.96, "btts_factor": 0.98, "draw_factor": 1.04, "variance_factor": 0.96},
    "La Liga": {"tempo_factor": 0.98, "over_factor": 0.98, "btts_factor": 0.99, "draw_factor": 1.02, "variance_factor": 0.98},
    "Ligue 1": {"tempo_factor": 1.01, "over_factor": 1.00, "btts_factor": 1.01, "draw_factor": 1.00, "variance_factor": 1.02},
    "Eredivisie": {"tempo_factor": 1.15, "over_factor": 1.12, "btts_factor": 1.08, "draw_factor": 0.92, "variance_factor": 1.08},
}


class LeagueProfileEngine:
    def get_profile(self, league_name):
        league_name = str(league_name or "")
        for key, profile in LEAGUE_PROFILES.items():
            if key.lower() in league_name.lower():
                return profile
        return DEFAULT_PROFILE

    def adjust_probability(self, probability, league_name, market):
        try:
            probability = float(probability)
            if probability > 1:
                probability = probability / 100
            profile = self.get_profile(league_name)
            market = str(market or "").upper()
            factor = 1.00
            if "OVER" in market:
                factor *= profile["over_factor"]
            elif "BTTS" in market:
                factor *= profile["btts_factor"]
            elif "DRAW" in market:
                factor *= profile["draw_factor"]
            adjusted = probability * factor
            return round(max(0.03, min(0.97, adjusted)), 4)
        except Exception:
            return probability
