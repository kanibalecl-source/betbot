"""Full V3 pipeline: independent prediction -> calibration -> bookmaker comparison -> decision.
"""
from __future__ import annotations

from typing import Dict
from feature_builder_v3 import FeatureBuilderV3
from core_predictive_engine_v3 import CorePredictiveEngineV3
from adaptive_learning_engine_v3 import AdaptiveLearningEngineV3
from market_comparison_engine_v3 import MarketComparisonEngineV3


class FullAutoPipelineV3:
    def __init__(self):
        self.features = FeatureBuilderV3()
        self.core = CorePredictiveEngineV3()
        self.learning = AdaptiveLearningEngineV3()
        self.market = MarketComparisonEngineV3()

    def analyze_pick(self, match: Dict, market_code: str, bookmaker_odds=None) -> Dict:
        home_xg, away_xg, meta = self.features.build_xg(match)
        raw_prob = self.core.predict_market(market_code, home_xg, away_xg)
        if raw_prob is None:
            return {'status': 'REJECTED', 'reason': 'UNSUPPORTED_MARKET', 'market': market_code}
        calibrated = self.learning.calibrate_probability(raw_prob, match.get('league', ''), market_code)
        result = {
            'status': 'MODEL_READY',
            'market': market_code,
            'home_xg_v3': home_xg,
            'away_xg_v3': away_xg,
            'model_probability_raw': raw_prob,
            'model_probability': calibrated,
            'confidence_percent': round(calibrated * 100, 2),
            **meta,
            'top_scores': self.core.most_likely_scores(home_xg, away_xg, top_n=5),
        }
        if bookmaker_odds:
            result.update(self.market.compare_single(calibrated, bookmaker_odds))
            result['status'] = self.decision(result)
        return result

    def decision(self, r: Dict) -> str:
        if r.get('data_quality', 0) < 0.30:
            return 'REJECTED_LOW_DATA_QUALITY'
        if r.get('ev_decimal') is None:
            return 'MODEL_ONLY_NO_ODDS'
        if r.get('ev_decimal', -1) >= 0.06 and r.get('edge_decimal', -1) >= 0.04 and r.get('model_probability', 0) >= 0.52:
            return 'ACCEPTED_VALUE'
        return 'REJECTED_NO_VALUE'
