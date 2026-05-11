"""Automated learning from settled bets.
Uses calibrated empirical performance by market/league buckets with Bayesian shrinkage.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)
RESULTS_FILE = DATA_DIR / 'history_results.csv'
CALIBRATION_FILE = DATA_DIR / 'calibration_v3.csv'


class AdaptiveLearningEngineV3:
    def __init__(self, prior_alpha: float = 8, prior_beta: float = 8):
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta

    def load_results(self) -> pd.DataFrame:
        if not RESULTS_FILE.exists():
            return pd.DataFrame()
        return pd.read_csv(RESULTS_FILE)

    def build_calibration_table(self) -> pd.DataFrame:
        df = self.load_results()
        if df.empty:
            return pd.DataFrame()
        # Normalize common columns
        if 'settlement' not in df.columns:
            return pd.DataFrame()
        if 'market' not in df.columns and 'kod_rynku' in df.columns:
            df['market'] = df['kod_rynku']
        if 'model_probability' not in df.columns:
            for c in ['probability', 'prawd_model', 'final_probability']:
                if c in df.columns:
                    df['model_probability'] = df[c]
                    break
        if 'model_probability' not in df.columns:
            return pd.DataFrame()
        df['won'] = df['settlement'].astype(str).str.upper().isin(['WIN', 'WON']).astype(int)
        df['model_probability'] = pd.to_numeric(df['model_probability'], errors='coerce')
        df.loc[df['model_probability'] > 1, 'model_probability'] = df['model_probability'] / 100.0
        df = df.dropna(subset=['model_probability', 'market'])
        if df.empty:
            return pd.DataFrame()
        df['prob_bucket'] = pd.cut(df['model_probability'], bins=[0, .45, .55, .65, .75, .85, 1.0], labels=['0-45','45-55','55-65','65-75','75-85','85-100'], include_lowest=True)
        group_cols = ['market', 'prob_bucket']
        if 'league' in df.columns:
            group_cols = ['league', 'market', 'prob_bucket']
        g = df.groupby(group_cols, dropna=False).agg(
            bets=('won', 'count'), wins=('won', 'sum'), avg_model_prob=('model_probability', 'mean')
        ).reset_index()
        g['empirical_hit_rate'] = g['wins'] / g['bets']
        g['bayes_hit_rate'] = (g['wins'] + self.prior_alpha) / (g['bets'] + self.prior_alpha + self.prior_beta)
        g['calibration_error'] = g['bayes_hit_rate'] - g['avg_model_prob']
        g.to_csv(CALIBRATION_FILE, index=False)
        return g

    def calibrate_probability(self, probability: float, league: str = '', market: str = '') -> float:
        p = float(probability)
        if p > 1: p /= 100.0
        if not CALIBRATION_FILE.exists():
            return max(0.01, min(0.99, p))
        table = pd.read_csv(CALIBRATION_FILE)
        if table.empty or 'calibration_error' not in table.columns:
            return max(0.01, min(0.99, p))
        # Find closest rows by league/market first, then market only
        candidates = table
        if league and 'league' in candidates.columns:
            exact = candidates[(candidates['league'].astype(str) == str(league)) & (candidates['market'].astype(str) == str(market))]
            if not exact.empty:
                candidates = exact
            else:
                candidates = candidates[candidates['market'].astype(str) == str(market)]
        else:
            candidates = candidates[candidates['market'].astype(str) == str(market)] if 'market' in candidates.columns else candidates
        if candidates.empty:
            return max(0.01, min(0.99, p))
        # weighted average correction, capped
        candidates['bets'] = pd.to_numeric(candidates['bets'], errors='coerce').fillna(0)
        candidates['calibration_error'] = pd.to_numeric(candidates['calibration_error'], errors='coerce').fillna(0)
        correction = (candidates['calibration_error'] * candidates['bets']).sum() / max(candidates['bets'].sum(), 1)
        correction = max(-0.08, min(0.08, correction))
        return round(max(0.01, min(0.99, p + correction)), 6)
