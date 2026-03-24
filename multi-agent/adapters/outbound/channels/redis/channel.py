"""
Redis Streams session channel — write side.

Each emit() appends an event to a Redis Stream keyed by session ID.
Streams persist events so that late-joining readers get full replay.

Control signals (close) use a separate field so that user data in
the payload field is never polluted.

TTL is configurable; set to 0 to persist streams forever.
"""
import json
import threading
from typing import Any

from pydantic.json import pydantic_encoder
from redis import Redis

from mas.core.channels import SessionChannel
from .constants import STREAM_PREFIX, ACTIVE_SESSIONS_KEY, StreamField, ControlSignal


class RedisSessionChannel(SessionChannel):

    def __init__(self, session_id: str, redis_client: Redis, ttl: int = 3600) -> None:
        self._session_id = session_id
        self._redis = redis_client
        self._stream_key = f"{STREAM_PREFIX}{session_id}"
        self._ttl = ttl
        self._closed = False
        self._close_lock = threading.Lock()
        self._redis.sadd(ACTIVE_SESSIONS_KEY, session_id)

    @property
    def session_id(self) -> str:
        return self._session_id

    def emit(self, data: Any) -> None:
        if self._closed:
            return
        self._redis.xadd(
            self._stream_key,
            {StreamField.PAYLOAD: json.dumps(data, default=pydantic_encoder)},
        )
        self._touch_ttl()

    def is_active(self) -> bool:
        return not self._closed

    def close(self) -> None:
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
        self._redis.xadd(
            self._stream_key,
            {StreamField.CONTROL: ControlSignal.CLOSE},
        )
        self._redis.srem(ACTIVE_SESSIONS_KEY, self._session_id)
        self._redis.delete(self._stream_key)

    def supports_input(self) -> bool:
        return True

    def _touch_ttl(self) -> None:
        if self._ttl > 0:
            self._redis.expire(self._stream_key, self._ttl)
