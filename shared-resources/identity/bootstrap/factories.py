from __future__ import annotations
from flask import Flask
from config.app_config import AppConfig
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from utils.auth_manager import AuthManager
    from adapters.outbound.redis.redis_kv_store import RedisKVStore

def build_auth_stack(app: Flask, config: AppConfig) -> AuthManager:
    """Wire Redis + AuthManager after logging is configured (lazy import of AuthManager)."""
    from utils.auth_manager import AuthManager
    #build redis store
    redis_store = build_redis_store(config)
    # Initialize Authentication Manager    
    return AuthManager(app, redis_store)

def build_redis_store(config: AppConfig) -> RedisKVStore:
    from adapters.outbound.redis.redis_kv_store import RedisKVStore
    redis_store = RedisKVStore(
        host=config.redis_ip,
        port=config.redis_port,
        db=config.redis_db,
        password=config.redis_password,
        decode_responses=config.redis_decode_responses,
    )
    return redis_store
