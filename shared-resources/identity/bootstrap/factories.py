from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Flask

from config.app_config import AppConfig
from global_utils.redis import RedisKVStore, build_redis_client

if TYPE_CHECKING:
    from utils.auth_manager import AuthManager


def build_auth_stack(app: Flask, config: AppConfig) -> AuthManager:
    """Wire Redis + AuthManager after logging is configured (lazy import of AuthManager)."""
    from utils.auth_manager import AuthManager

    redis_store = build_redis_store(config)
    return AuthManager(app, redis_store)


def build_redis_store(config: AppConfig) -> RedisKVStore:
    client = build_redis_client(config.redis_db)
    return RedisKVStore(client)
