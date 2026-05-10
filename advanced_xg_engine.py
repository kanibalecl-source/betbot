class AdvancedXGEngine:
    def weighted_team_xg(self, season_xg_for=1.2, season_xg_against=1.2, recent_xg_for=1.2, recent_xg_against=1.2, home_away_xg_for=1.2, home_away_xg_against=1.2, attack_weight=0.58, defense_weight=0.42):
        try:
            attack = float(season_xg_for) * 0.25 + float(recent_xg_for) * 0.45 + float(home_away_xg_for) * 0.30
            defense = float(season_xg_against) * 0.25 + float(recent_xg_against) * 0.45 + float(home_away_xg_against) * 0.30
            return round(max((attack * attack_weight) + (defense * defense_weight), 0.05), 3)
        except Exception as e:
            print(f"ADVANCED XG ERROR: {e}")
            return 1.20

    def match_total_xg(self, home_xg, away_xg):
        try:
            return round(float(home_xg) + float(away_xg), 3)
        except Exception:
            return 2.40

    def over_probability_from_xg(self, total_xg, line=2.5):
        try:
            total_xg = float(total_xg)
            if line == 1.5:
                base = 1 - pow(2.718281828, -total_xg) * (1 + total_xg)
            else:
                base = 1 - pow(2.718281828, -total_xg) * (1 + total_xg + (total_xg ** 2) / 2)
            return round(max(0.03, min(0.97, base)), 4)
        except Exception:
            return 0.50
