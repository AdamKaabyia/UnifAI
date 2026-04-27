"""
RedisFlowStateStore — implements :class:`FlowStateStore` using Redis.

Keys: ``auth_pending:<state_hash>``
TTL:  derived from ``flow_state.expires_at``
Consume: atomic ``GETDEL`` (Redis 6.2+)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from mas.core.auth.schemes.oauth2.models import FlowState, FlowStateStore

logger = logging.getLogger(__name__)

_PREFIX = "auth_pending:"


class RedisFlowStateStore(FlowStateStore):

    def __init__(self, redis_client):
        self._redis = redis_client

    def save(self, flow_state: FlowState) -> None:
        key = f"{_PREFIX}{flow_state.state_hash}"
        ttl = max(
            int((flow_state.expires_at - datetime.now(timezone.utc)).total_seconds()),
            60,
        )
        payload = flow_state.model_dump(mode="json")
        self._redis.setex(key, ttl, json.dumps(payload))

    def consume(self, state_hash: str) -> Optional[FlowState]:
        key = f"{_PREFIX}{state_hash}"
        raw = self._redis.getdel(key)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return FlowState.model_validate(data)
        except Exception as exc:
            logger.error("Failed to parse pending auth from Redis: %s", exc)
            return None
