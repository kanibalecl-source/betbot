from datetime import datetime
from pydantic import BaseModel, Field, field_validator

class PredictionInput(BaseModel):
    home_team: str = Field(..., min_length=1)
    away_team: str = Field(..., min_length=1)
    league: str | None = None
    market: str | None = None
    odds: float = Field(..., gt=1.0)
    probability: float | None = Field(default=None, ge=0, le=1)
    home_xg: float | None = Field(default=None, ge=0)
    away_xg: float | None = Field(default=None, ge=0)
    minute: int | None = Field(default=None, ge=0, le=130)
    pressure: float | None = Field(default=None, ge=0)
    momentum: float | None = None

    @field_validator("probability", mode="before")
    @classmethod
    def normalize_probability(cls, value):
        if value is None:
            return value
        value = float(value)
        return value / 100 if value > 1 else value

class PredictionOutput(BaseModel):
    model_version: str
    match_name: str
    market: str
    probability: float
    fair_odds: float
    bookmaker_odds: float
    edge: float
    ev: float
    confidence: float
    risk_level: str
    recommendation: str
    stake_pct: float
    generated_at: datetime

class BetCreate(BaseModel):
    pick_id: str
    stake: float = Field(..., gt=0)

class HealthResponse(BaseModel):
    ok: bool
    app: str
    environment: str
    model_version: str


class RealtimeEvent(BaseModel):
    event_id: str
    event_type: str
    payload: dict
    created_at: datetime

class RealtimeSnapshot(BaseModel):
    ok: bool
    events: list[RealtimeEvent]
    cache_size: int
    mode: str
