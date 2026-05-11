from __future__ import annotations

from typing import Dict, Any, Optional

from .config import RocketConfig, load_config
from .data_hub import DataHubV4
from .feature_factory import FeatureFactoryV4
from .xg_engine import XGEngineV4
from .simulation_engine import SimulationEngineV4
from .learning_engine import LearningEngineV4
from .market_engine import MarketComparatorV4
from .risk_engine import RiskEngineV4


class RocketOrchestratorV4:
    """End-to-end autonomous prediction pipeline.

    Flow:
    1. Merge and score data quality.
    2. Build independent features.
    3. Estimate xG from shots or features.
    4. Simulate markets from xG.
    5. Calibrate probability with historical self-learning.
    6. Compare to bookmaker only at the end.
    7. Decide value and stake.
    """

    def __init__(self, config: Optional[RocketConfig] = None, bankroll: float = 1000.0):
        self.config = config or load_config()
        self.hub = DataHubV4(self.config)
        self.features = FeatureFactoryV4()
        self.xg = XGEngineV4()
        self.sim = SimulationEngineV4(max_goals=self.config.max_goals)
        self.learn = LearningEngineV4(self.config)
        self.market = MarketComparatorV4()
        self.risk = RiskEngineV4(bankroll=bankroll, fractional_kelly=self.config.fractional_kelly, max_single_stake_pct=self.config.max_single_stake_pct)

    def analyze(self, match: Dict[str, Any], market: str, bookmaker_odds: Optional[float] = None, bankroll: Optional[float] = None) -> Dict[str, Any]:
        qr = self.hub.quality_report(match)
        f = self.features.build(match, data_quality=qr.score)
        shot_result = self.xg.from_shots(match.get("events", []), f.home_team, f.away_team)
        xgr = shot_result or self.xg.pre_match_xg(f)
        probs = self.sim.markets(xgr.home_xg, xgr.away_xg)
        mkey = str(market).upper().replace('.', '_')
        raw_p = probs.get(mkey)
        if raw_p is None:
            return {"status": "REJECTED_UNSUPPORTED_MARKET", "market": market, "supported_markets": sorted(probs)}
        calibrated = self.learn.calibrate(raw_p, f.league, mkey)
        result = {
            "status": "MODEL_ONLY",
            "league": f.league,
            "home_team": f.home_team,
            "away_team": f.away_team,
            "market": mkey,
            "home_xg": xgr.home_xg,
            "away_xg": xgr.away_xg,
            "xg_method": xgr.method,
            "xg_explain": xgr.explain,
            "model_probability_raw": raw_p,
            "model_probability": calibrated,
            "confidence_percent": round(calibrated*100, 2),
            "top_scores": self.sim.top_scores(xgr.home_xg, xgr.away_xg),
            "data_quality": qr.score,
            "sources_used": qr.sources_used,
            "data_warnings": qr.warnings,
            "features": f.to_dict(),
        }
        if qr.score < self.config.min_data_quality:
            result["status"] = "REJECTED_LOW_DATA_QUALITY"
        if bookmaker_odds is not None:
            comp = self.market.compare(calibrated, bookmaker_odds)
            result.update(comp)
            if result["status"] != "REJECTED_LOW_DATA_QUALITY":
                if comp.get("ev_decimal", -9) >= self.config.min_ev and comp.get("edge_decimal", -9) >= self.config.min_edge and calibrated >= self.config.min_model_prob:
                    if bankroll is not None:
                        self.risk.bankroll = float(bankroll)
                    result.update(self.risk.stake(calibrated, bookmaker_odds, qr.score))
                    result["status"] = "ACCEPTED_VALUE"
                else:
                    result["status"] = "REJECTED_NO_VALUE"
        return result
