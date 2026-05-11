"""Rocket V4 autonomous predictive stack for BetBot.

Bookmaker odds are never used to create model probabilities. They are only used
in MarketComparatorV4 to decide whether the model has value.
"""

__all__ = [
    "config", "probability", "data_hub", "feature_factory", "xg_engine",
    "simulation_engine", "market_engine", "learning_engine", "settlement",
    "risk_engine", "orchestrator",
]
