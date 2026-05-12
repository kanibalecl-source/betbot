from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from .multi_source import MultiSourceHubV5
from .advanced_xg import AdvancedXGEngineV5
from .monte_carlo import MonteCarloEngineV5
from .ml_engine import LightweightMLEngineV5
from .meta_model import MetaModelAIV5
from .live_intelligence import LiveIntelligenceEngineV5
from .market_only_comparison import MarketOnlyComparatorV5
from .utils import num


class RocketPipelineV5:
    """Full V5 pipeline.

    Flow:
    multi-source data -> advanced xG -> Monte Carlo -> ML adjustment -> live adjustment
    -> meta-model final probability -> bookmaker comparison only at the end.
    """

    def __init__(self, data_dir: str = "data/rocket_v5", monte_carlo_runs: int = 75000):
        self.hub = MultiSourceHubV5(data_dir)
        self.xg = AdvancedXGEngineV5()
        self.mc = MonteCarloEngineV5(runs=monte_carlo_runs)
        self.ml = LightweightMLEngineV5(data_dir)
        self.meta = MetaModelAIV5(data_dir)
        self.live = LiveIntelligenceEngineV5()
        self.market = MarketOnlyComparatorV5()

    def analyze(self, payloads: Iterable[Dict[str, Any]] | Dict[str, Any], market: str = "OVER_2_5",
                bookmaker_odds: Optional[float] = None, live_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if isinstance(payloads, dict):
            match = payloads
        else:
            match = self.hub.merge_payloads(payloads)
        audit = self.hub.audit(match)
        match["data_quality"] = audit.score
        self.hub.save_snapshot(match)

        xg = self.xg.calculate(match, data_quality=audit.score)
        live_signal = None
        hxg = xg.home_xg
        axg = xg.away_xg
        live_adjustment = 0.0
        if live_payload:
            live_signal = self.live.evaluate(live_payload)
            hxg *= live_signal.home_xg_multiplier
            axg *= live_signal.away_xg_multiplier
            live_adjustment = live_signal.probability_adjustment

        sim = self.mc.simulate(hxg, axg)
        raw_prob = sim.markets.get(market)
        if raw_prob is None:
            return {"status": "UNSUPPORTED_MARKET", "market": market, "supported_markets": sorted(sim.markets)}

        features = self.ml.build_features(match, {**xg.to_dict(), "home_xg": hxg, "away_xg": axg})
        ml_adjustment = self.ml.predict_adjustment(features)
        meta = self.meta.combine(
            simulation_prob=raw_prob,
            ml_adjustment=ml_adjustment,
            calibration_adjustment=num(match.get("calibration_adjustment"), 0.0),
            live_adjustment=live_adjustment,
            league=str(match.get("league", "GLOBAL")),
            market=market,
            data_quality=audit.score,
        )

        result: Dict[str, Any] = {
            "status": "MODEL_READY_NO_ODDS" if not bookmaker_odds else "MODEL_READY_WITH_MARKET_CHECK",
            "match": {"home_team": match.get("home_team"), "away_team": match.get("away_team"), "league": match.get("league")},
            "market": market,
            "probability": meta["probability"],
            "xg": {**xg.to_dict(), "live_adjusted_home_xg": round(hxg, 4), "live_adjusted_away_xg": round(axg, 4)},
            "simulation": sim.to_dict(),
            "ml": {"features": features, "adjustment": ml_adjustment, "trained_samples": self.ml.state.get("trained_samples", 0)},
            "meta": meta,
            "data_audit": audit.__dict__,
            "live_signal": live_signal.to_dict() if live_signal else None,
            "bookmaker_rule": "odds are ignored before this point; used only for EV/edge comparison",
        }
        if bookmaker_odds:
            result["market_comparison"] = self.market.compare(meta["probability"], bookmaker_odds)
            result["status"] = result["market_comparison"]["status"]
        return result
