from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    app_name: str = "BetBot Pro"
    environment: str = Field(default="production", pattern="^(local|test|staging|production)$")
    log_level: str = "INFO"
    api_key: str | None = None
    betting_enabled: bool = False
    database_url: str = "sqlite:///data/bot_tracker.sqlite3"
    cors_origins: str = ""
    max_stake_pct: float = 0.0025
    min_edge: float = 0.03
    model_version: str = "10.0.0"
    realtime_enabled: bool = True
    realtime_tick_seconds: float = 1.0
    realtime_cache_ttl_seconds: int = 30
    realtime_max_events: int = 500
    realtime_publish_per_minute: int = 30
    realtime_max_connections_per_ip: int = 3
    realtime_max_payload_bytes: int = 65536
    redis_url: str | None = None
    postgres_dsn: str | None = None
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()
