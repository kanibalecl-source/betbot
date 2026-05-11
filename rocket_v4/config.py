from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os


@dataclass
class DataProviderConfig:
    name: str
    base_url: str = ""
    api_key_env: str = ""
    priority: int = 50
    enabled: bool = True
    notes: str = ""


@dataclass
class RocketConfig:
    data_dir: Path = field(default_factory=lambda: Path("data/rocket_v4"))
    min_data_quality: float = 0.55
    min_ev: float = 0.045
    min_edge: float = 0.035
    min_model_prob: float = 0.50
    max_single_stake_pct: float = 0.015
    fractional_kelly: float = 0.20
    max_goals: int = 10
    monte_carlo_runs: int = 50000
    providers: list[DataProviderConfig] = field(default_factory=lambda: [
        DataProviderConfig("api_football", api_key_env="API_FOOTBALL_KEY", priority=10, notes="fixtures, results, lineups, events, stats"),
        DataProviderConfig("football_data", api_key_env="FOOTBALL_DATA_KEY", priority=30, notes="fixtures/results backup"),
        DataProviderConfig("understat_or_xg_source", priority=20, notes="shot based xG if available"),
        DataProviderConfig("sofascore_unofficial", priority=40, notes="live momentum, attacks, lineups; respect ToS"),
        DataProviderConfig("open_meteo", priority=60, notes="weather context"),
    ])

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for sub in ["raw", "features", "models", "reports", "settlement"]:
            (self.data_dir / sub).mkdir(exist_ok=True)


def load_config() -> RocketConfig:
    cfg = RocketConfig()
    cfg.ensure_dirs()
    return cfg


def env_key(name: str) -> str:
    return os.getenv(name, "")
