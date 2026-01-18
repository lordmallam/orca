"""
Configuration management for AIS Viewer backend services.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # AIS Stream API
    aisstream_api_key: str = ""
    aisstream_url: str = "wss://stream.aisstream.io/v0/stream"

    # Database
    postgres_password: str = ""
    postgres_user: str = ""
    postgres_db: str = ""
    postgres_host: str = ""
    postgres_port: int = 5432

    # Ingest Service
    batch_size: int = 1000
    batch_interval_seconds: int = 3

    # API Service
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
