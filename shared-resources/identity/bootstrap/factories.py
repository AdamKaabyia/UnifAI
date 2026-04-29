from __future__ import annotations
from typing import TYPE_CHECKING
from flask import Flask
from config.app_config import AppConfig
from global_utils.redis import RedisKVStore, build_redis_client
import logging

if TYPE_CHECKING:
    from utils.auth_manager import AuthManager

logger = logging.getLogger("auth_manager")

def build_auth_stack(app: Flask, config: AppConfig) -> AuthManager:
    """Wire Redis + AuthManager after logging is configured (lazy import of AuthManager)."""
    from utils.auth_manager import AuthManager
    
    try:
        redis_store = build_redis_store(config)
        auth_stack = AuthManager(app, redis_store)
        logger.info("Auth stack built successfully")
        return auth_stack
    except Exception as e:
        logger.error(f"Failed to build auth stack: {e}")
        raise


def build_redis_store(config: AppConfig) -> RedisKVStore:
    client = build_redis_client(config.redis_db)
    return RedisKVStore(client)
