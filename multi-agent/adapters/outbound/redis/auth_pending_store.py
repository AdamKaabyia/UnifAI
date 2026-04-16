"""
RedisPendingStore — implements :class:`PendingStore` using Redis.

Keys: ``auth_pending:<state_hash>``
TTL:  derived from ``pending.expires_at``
Consume: atomic ``GETDEL`` (Redis 6.2+)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from mas.core.auth.protocols.oauth2.models import PendingAuth, PendingStore

logger = logging.getLogger(__name__)

_PREFIX = "auth_pending:"


class RedisPendingStore(PendingStore):

    def __init__(self, redis_client):
        self._redis = redis_client

    def save(self, pending: PendingAuth) -> None:
        key = f"{_PREFIX}{pending.state_hash}"
        ttl = max(
            int((pending.expires_at - datetime.now(timezone.utc)).total_seconds()),
            60,
        )
        payload = pending.model_dump(mode="json")
        self._redis.setex(key, ttl, json.dumps(payload))

    def consume(self, state_hash: str) -> Optional[PendingAuth]:
        key = f"{_PREFIX}{state_hash}"
        raw = self._redis.getdel(key)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return PendingAuth.model_validate(data)
        except Exception as exc:
            logger.error("Failed to parse pending auth from Redis: %s", exc)
            return None
