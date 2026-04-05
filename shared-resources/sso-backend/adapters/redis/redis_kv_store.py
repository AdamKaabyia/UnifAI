from __future__ import annotations

from typing import Optional

import redis

from ports.kv_store import KVStore


class RedisKVStore(KVStore):
    """Redis implementation of the KVStore port (hexagonal adapter)."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        db: int = 0,
        password: Optional[str] = None,
        decode_responses: bool = True,
    ) -> None:
        self._client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=decode_responses,
        )

    def get(self, key: str) -> Optional[str]:
        raw = self._client.get(key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            return raw.decode("utf-8")
        return str(raw)

    def set(self, key: str, value: any, ttl_seconds: Optional[int] = None) -> None:
        if ttl_seconds is not None:
            self._client.set(key, value, ex=ttl_seconds)
        else:
            self._client.set(key, value)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def ping(self) -> bool:
        return self._client.ping()
