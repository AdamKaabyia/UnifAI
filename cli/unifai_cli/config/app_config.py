"""CLI application configuration."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """CLI configuration — resolved from environment variables or defaults."""

    mas_url: str = "http://10.46.254.131:8002"
    api_prefix: str = "/api"

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    @lru_cache()
    def get_instance(cls) -> "AppConfig":
        return cls()
