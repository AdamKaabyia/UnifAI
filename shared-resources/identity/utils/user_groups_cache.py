"""
Redis-backed cache for user ROVER/directory group memberships.

On each SSO login we look up the user's groups and store them in Redis
with a TTL. Subsequent reads (e.g. listing teams that include the user's
groups) hit the cache instead of making LDAP calls.
"""
import json
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 3600  # 1 hour


class UserGroupsCache:
    """Thin wrapper around a Redis connection for user-group data."""

    KEY_PREFIX = "unifai:user_groups:"

    def __init__(self, redis_client, ttl: int = _DEFAULT_TTL):
        self._redis = redis_client
        self._ttl = ttl

    def set_groups(self, username: str, groups: List[dict]) -> None:
        """Cache the group list for *username*."""
        key = self._key(username)
        try:
            self._redis.setex(key, self._ttl, json.dumps(groups))
            logger.debug("Cached %d groups for %s (ttl=%ds)", len(groups), username, self._ttl)
        except Exception:
            logger.exception("Failed to cache groups for %s", username)

    def get_groups(self, username: str) -> Optional[List[dict]]:
        """Return cached groups for *username*, or None if absent/expired."""
        key = self._key(username)
        try:
            raw = self._redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            logger.exception("Failed to read cached groups for %s", username)
            return None

    def invalidate(self, username: str) -> None:
        try:
            self._redis.delete(self._key(username))
        except Exception:
            logger.exception("Failed to invalidate group cache for %s", username)

    def _key(self, username: str) -> str:
        return f"{self.KEY_PREFIX}{username}"
