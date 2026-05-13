"""Feature builder for independent calculations.
It uses match/team data only. It must not use bookmaker odds.
"""
from __future__ import annotations

from typing import Dict, Tuple


def _num(value, default=0.0):
    try:
        if value is None:
            return default
        return float(str(value).replace(',', '.').replace('%', '').strip())
    except Exception:
        return default


class FeatureBuilderV3:
    def build_xg(self, match: Dict) -> Tuple[float, float, Dict]:
        # Direct xG if available from data provider
        home_xg = _num(match.get('home_xg') or match.get('xg_home') or match.get('home_expected_goals'), 0)
        away_xg = _num(match.get('away_xg') or match.get('xg_away') or match.get('away_expected_goals'), 0)
        source = 'direct_xg' if home_xg > 0 and away_xg > 0 else 'estimated_xg'

        if home_xg <= 0 or away_xg <= 0:
            # Conservative estimate from goals/form/stat fields. Better than neutral 0.50 fallback.
            h_attack = _num(match.get('home_goals_for_avg') or match.get('home_attack') or match.get('home_avg_goals_for'), 1.25)
            h_def = _num(match.get('home_goals_against_avg') or match.get('home_defense') or match.get('home_avg_goals_against'), 1.20)
            a_attack = _num(match.get('away_goals_for_avg') or match.get('away_attack') or match.get('away_avg_goals_for'), 1.15)
            a_def = _num(match.get('away_goals_against_avg') or match.get('away_defense') or match.get('away_avg_goals_against'), 1.25)
            league_avg = _num(match.get('league_avg_goals_team'), 1.35)
            home_adv = _num(match.get('home_advantage'), 1.08)
            home_xg = max(0.15, min(4.50, league_avg * (h_attack / league_avg) * (a_def / league_avg) * home_adv))
            away_xg = max(0.15, min(4.50, league_avg * (a_attack / league_avg) * (h_def / league_avg)))

        meta = {
            'xg_source': source,
            'data_quality': self.data_quality_score(match, source),
            'home_xg_v3': round(home_xg, 4),
            'away_xg_v3': round(away_xg, 4),
        }
        return round(home_xg, 4), round(away_xg, 4), meta

    def data_quality_score(self, match: Dict, source: str = '') -> float:
        important = [
            'home_xg', 'away_xg', 'home_id', 'away_id', 'league_id', 'fixture_id',
            'home_goals_for_avg', 'away_goals_for_avg', 'home_goals_against_avg', 'away_goals_against_avg',
            'shots_on_target', 'dangerous_attacks', 'possession'
        ]
        present = sum(1 for k in important if match.get(k) not in [None, '', 0, '0'])
        score = present / len(important)
        if source == 'direct_xg':
            score += 0.20
        return round(max(0.05, min(1.0, score)), 4)
