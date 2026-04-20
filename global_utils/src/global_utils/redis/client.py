"""
Redis client factory for shared services.

Uses :class:`~global_utils.config.config.SharedConfig` for connection settings.
The default entry point :func:`build_redis_client` returns a **single shared**
:class:`redis.Redis` instance per process (see implementation note below).
"""
from __future__ import annotations

import functools

from redis import Redis

from global_utils.config.config import SharedConfig


@functools.lru_cache(maxsize=1)
def build_redis_client() -> Redis:
    """
    Return a shared :class:`redis.Redis` client for this process.

    ``functools.lru_cache(maxsize=1)`` ensures the first call constructs the
    client and later calls return the **same** instance — a simple singleton
    without a custom class. For tests or reload scenarios you can call
    ``build_redis_client.cache_clear()`` before building again.

    Connection parameters come from :class:`~global_utils.config.config.SharedConfig`:
    ``redis_ip``, ``redis_port``, ``redis_db``, ``redis_password``,
    ``redis_decode_responses``.
    """
    config = SharedConfig.get_instance()
    return Redis(
        host=config.redis_ip,
        port=int(config.redis_port),
        db=config.redis_db,
        password=config.redis_password,
        decode_responses=config.redis_decode_responses,
    )
