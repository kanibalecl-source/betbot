import math
from datetime import datetime
from typing import Any, Literal
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
        value = value / 100 if value > 1 else value
        if not math.isfinite(value) or not 0 < value < 1:
            raise ValueError("probability must be finite and between 0 and 1")
        return value

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


Discipline = Literal["football", "volleyball", "handball"]


class SyncEnvelope(BaseModel):
    records: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    statuses: list[dict[str, Any]] = Field(default_factory=list, max_length=30)
    source: str = Field(default="betbot-main", min_length=1, max_length=80)


class SyncResult(BaseModel):
    accepted: int
    rejected: int
    statuses_saved: int
    rejection_reasons: dict[str, int]
    source_history_modified: bool = False
