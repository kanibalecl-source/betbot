from __future__ import annotations

from typing import Any, Dict, Optional

from advanced_calibration_analytics import AdvancedCalibrationAnalytics
from gpu_optimizer import GPUOptimizer
from ml_training_pipeline import MLTrainingPipeline
from multi_source_ingestion import MultiSourceIngestion
from source_quality_engine import SourceQualityEngine


class RocketV7EnterpriseOrchestrator:
    """Activates V7 enterprise stack in one callable pipeline."""

    def __init__(self, data_dir: str = "data/enterprise"):
        self.data_dir = data_dir
        self.ingestion = MultiSourceIngestion(data_dir="data")
        self.quality = SourceQualityEngine()
        self.gpu = GPUOptimizer(prefer_gpu=True)
        self.ml = MLTrainingPipeline(data_dir=data_dir)
        self.calibration = AdvancedCalibrationAnalytics(data_dir=data_dir)

    def analyze_fixture(self, fixture_id: str, home_xg: float, away_xg: float, market: str = "OVER_2_5", bookmaker_odds: Optional[float] = None) -> Dict[str, Any]:
        data = self.ingestion.fetch_fixture(fixture_id)
        q = data.get("source_quality", {}).get("quality_score", data.get("data_quality", 0.5))
        sim = self.gpu.vectorized_monte_carlo(home_xg, away_xg, runs=100000)
        market_map = {
            "HOME_WIN": sim["home_win"], "DRAW": sim["draw"], "AWAY_WIN": sim["away_win"],
            "OVER_0_5": sim["over_05"], "OVER_1_5": sim["over_15"], "OVER_2_5": sim["over_25"], "OVER_3_5": sim["over_35"], "OVER_4_5": sim["over_45"], "BTTS_YES": sim["btts_yes"],
        }
        raw_p = market_map.get(market, sim["over_25"])
        calibrated = self.calibration.apply(raw_p, market=market, league=str(data.get("league", "ALL")))
        ml_p = self.ml.predict_proba({"probability": calibrated, "home_xg": home_xg, "away_xg": away_xg, "data_quality": q, "odds": bookmaker_odds or 2.0})
        final_p = round(max(0.01, min(0.99, 0.68*calibrated + 0.32*ml_p)), 6)
        out: Dict[str, Any] = {
            "status": "V7_FULL_STACK_ACTIVE",
            "fixture_id": fixture_id,
            "market": market,
            "probability": final_p,
            "raw_probability": raw_p,
            "calibrated_probability": calibrated,
            "ml_probability": ml_p,
            "data_quality": q,
            "simulation": sim,
            "source_status": data.get("status"),
            "bookmaker_used_only_for_comparison": True,
        }
        if bookmaker_odds:
            fair_odds = round(1/final_p, 4)
            ev = final_p*float(bookmaker_odds)-1
            out["market_comparison"] = {"bookmaker_odds": bookmaker_odds, "fair_odds": fair_odds, "edge_ev": round(ev,6), "value": ev > 0.03}
        return out
