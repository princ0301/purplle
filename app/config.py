from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "info"
    store_layout_path: str = "./data/store_layout.json"
    pos_data_path: str = "./data/pos_transactions.csv"
    stale_feed_threshold_minutes: int = 10

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
