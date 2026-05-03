"""CLI application configuration."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """CLI configuration — resolved from environment variables or defaults."""

    mas_url: str = "http://10.46.254.131:8002"
    api_prefix: str = "/api"
    sso_url: str = "http://localhost:13456"

    # 0 means auto-select a free port; set via AUTH_CALLBACK_PORT env var or --callback-port flag
    auth_callback_port: int = 0

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
