from datetime import datetime, UTC
import os
from fastapi import HTTPException
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

        probability_value = legacy.get("prawd_final") or legacy.get("probability") or payload.probability
        if probability_value is None:
            raise HTTPException(
                status_code=422,
                detail="Brak zweryfikowanego prawdopodobieństwa rynku; kurs bota nie został wyliczony.",
            )
        probability = float(probability_value)
        if probability > 1:
            probability /= 100
        if not 0 < probability < 1:
            raise HTTPException(status_code=422, detail="Prawdopodobieństwo musi być w zakresie 0-1.")

        fair_odds = round(1 / probability, 3)
        edge = round((payload.odds * probability) - 1, 4)
        ev = round(edge * 100, 2)
        confidence = float(legacy.get("confidence") or legacy.get("confidence_score") or probability * 100)
        risk_level = str(legacy.get("risk_level") or ("LOW" if edge >= 0.08 and confidence >= 65 else "MEDIUM" if edge >= 0.03 else "HIGH"))
        recommendation = "BET" if edge >= self.settings.min_edge and risk_level in {"LOW", "MEDIUM"} else "PASS"
        stake_pct = min(self.settings.max_stake_pct, max(0.0, edge / 10)) if recommendation == "BET" else 0.0

        output = PredictionOutput(
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
        if os.getenv("BETBOT_QUALITY_SHADOW", "0").strip().lower() in {"1", "true", "yes", "on"}:
            try:
                from app.services.safe_upgrades.shadow_mode import run_shadow_mode
                run_shadow_mode(raw, output.model_dump(mode="json"))
            except Exception:
                # Shadow diagnostics must never alter or interrupt a prediction.
                pass
        return output
