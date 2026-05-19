from datetime import datetime, UTC
from app.core.config import get_settings
from app.domain.schemas import PredictionInput, PredictionOutput

try:
    from master_prediction_engine import MasterPredictionEngine
except Exception:  # pragma: no cover
    MasterPredictionEngine = None

class PredictionService:
    def __init__(self):
        self.settings = get_settings()
        self.legacy_engine = MasterPredictionEngine() if MasterPredictionEngine else None

    def predict(self, payload: PredictionInput) -> PredictionOutput:
        raw = payload.model_dump(exclude_none=True)
        raw.update({
            "home": payload.home_team,
            "away": payload.away_team,
            "kurs_buk": payload.odds,
            "odds": payload.odds,
        })
        legacy = self.legacy_engine.process_match(raw) if self.legacy_engine else {}

        probability = float(legacy.get("prawd_final") or legacy.get("probability") or payload.probability or 0.5)
        if probability > 1:
            probability /= 100
        probability = max(0.01, min(0.99, probability))

        fair_odds = round(1 / probability, 3)
        edge = round((payload.odds * probability) - 1, 4)
        ev = round(edge * 100, 2)
        confidence = float(legacy.get("confidence") or legacy.get("confidence_score") or probability * 100)
        risk_level = str(legacy.get("risk_level") or ("LOW" if edge >= 0.08 and confidence >= 65 else "MEDIUM" if edge >= 0.03 else "HIGH"))
        recommendation = "BET" if edge >= self.settings.min_edge and risk_level in {"LOW", "MEDIUM"} else "PASS"
        stake_pct = min(self.settings.max_stake_pct, max(0.0, edge / 10)) if recommendation == "BET" else 0.0

        return PredictionOutput(
            model_version=self.settings.model_version,
            match_name=f"{payload.home_team} vs {payload.away_team}",
            market=payload.market or raw.get("market") or "UNKNOWN",
            probability=round(probability, 4),
            fair_odds=fair_odds,
            bookmaker_odds=payload.odds,
            edge=edge,
            ev=ev,
            confidence=round(confidence, 2),
            risk_level=risk_level,
            recommendation=recommendation,
            stake_pct=round(stake_pct, 4),
            generated_at=datetime.now(UTC),
        )
