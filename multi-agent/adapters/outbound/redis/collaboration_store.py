"""
Redis-backed collaboration store.

Data structures:
    mas:collab:session:{session_id}:participants  — Hash { user_id → JSON(Participant) }
    mas:collab:session:{session_id}:presence:{uid} — String with TTL (heartbeat sentinel)
    mas:collab:team:{team_id}:sessions            — Set of session_ids
    mas:collab:user:{user_id}:sessions            — Set of session_ids

Presence is maintained via per-user keys with a TTL.  Participants whose
presence key has expired are lazily pruned on the next ``get_participants``
call so that stale entries never accumulate.
"""
import json
import logging
from datetime import datetime, timezone
from typing import List

from redis import ConnectionPool, Redis
from redis.exceptions import RedisError

from mas.collaboration.models import (
    Participant,
    ParticipantRole,
    SessionParticipants,
    TeamSessionIndex,
)
from mas.collaboration.ports import CollaborationStore

logger = logging.getLogger(__name__)

_PREFIX = "mas:collab:"


def _participants_key(session_id: str) -> str:
    return f"{_PREFIX}session:{session_id}:participants"


def _presence_key(session_id: str, user_id: str) -> str:
    return f"{_PREFIX}session:{session_id}:presence:{user_id}"


def _team_sessions_key(team_id: str) -> str:
    return f"{_PREFIX}team:{team_id}:sessions"


def _user_sessions_key(user_id: str) -> str:
    return f"{_PREFIX}user:{user_id}:sessions"


class RedisCollaborationStore(CollaborationStore):

    def __init__(self, redis_url: str) -> None:
        self._pool = ConnectionPool.from_url(redis_url)

    def _client(self) -> Redis:
        return Redis(connection_pool=self._pool)

    # ── Participant presence ────────────────────────────────────────

    def add_participant(
        self,
        session_id: str,
        participant: Participant,
        ttl: int = 300,
    ) -> None:
        r = self._client()
        pipe = r.pipeline(transaction=False)

        pipe.hset(
            _participants_key(session_id),
            participant.user_id,
            participant.model_dump_json(),
        )
        pipe.set(
            _presence_key(session_id, participant.user_id),
            "1",
            ex=ttl,
        )
        pipe.sadd(_user_sessions_key(participant.user_id), session_id)

        pipe.execute()

    def remove_participant(self, session_id: str, user_id: str) -> None:
        r = self._client()
        pipe = r.pipeline(transaction=False)

        pipe.hdel(_participants_key(session_id), user_id)
        pipe.delete(_presence_key(session_id, user_id))
        pipe.srem(_user_sessions_key(user_id), session_id)

        pipe.execute()

    def heartbeat(self, session_id: str, user_id: str, ttl: int = 300) -> None:
        r = self._client()
        r.set(_presence_key(session_id, user_id), "1", ex=ttl)

    def get_participants(self, session_id: str) -> SessionParticipants:
        """
        Return participants whose presence sentinel is still alive.
        Lazily prunes expired entries from the hash.
        """
        r = self._client()
        raw = r.hgetall(_participants_key(session_id))
        if not raw:
            return SessionParticipants(session_id=session_id)

        alive: list[Participant] = []
        expired_uids: list[str] = []

        for uid_bytes, data_bytes in raw.items():
            uid = uid_bytes.decode() if isinstance(uid_bytes, bytes) else uid_bytes
            if r.exists(_presence_key(session_id, uid)):
                data = json.loads(data_bytes)
                alive.append(Participant.model_validate(data))
            else:
                expired_uids.append(uid)

        if expired_uids:
            pipe = r.pipeline(transaction=False)
            for uid in expired_uids:
                pipe.hdel(_participants_key(session_id), uid)
                pipe.srem(_user_sessions_key(uid), session_id)
            pipe.execute()

        return SessionParticipants(session_id=session_id, participants=alive)

    # ── Team-session index ──────────────────────────────────────────

    def register_team_session(self, team_id: str, session_id: str) -> None:
        self._client().sadd(_team_sessions_key(team_id), session_id)

    def unregister_team_session(self, team_id: str, session_id: str) -> None:
        self._client().srem(_team_sessions_key(team_id), session_id)

    def get_team_sessions(self, team_id: str) -> TeamSessionIndex:
        members = self._client().smembers(_team_sessions_key(team_id))
        ids = [m.decode() if isinstance(m, bytes) else m for m in members]
        return TeamSessionIndex(team_id=team_id, active_session_ids=ids)

    # ── User-to-sessions mapping ────────────────────────────────────

    def get_user_sessions(self, user_id: str) -> List[str]:
        members = self._client().smembers(_user_sessions_key(user_id))
        return [m.decode() if isinstance(m, bytes) else m for m in members]

    # ── Typing indicators ────────────────────────────────────────────

    @staticmethod
    def _typing_key(session_id: str, user_id: str) -> str:
        return f"{_PREFIX}session:{session_id}:typing:{user_id}"

    @staticmethod
    def _typing_pattern(session_id: str) -> str:
        return f"{_PREFIX}session:{session_id}:typing:*"

    def set_typing(self, session_id: str, user_id: str, ttl: int = 5) -> None:
        self._client().set(self._typing_key(session_id, user_id), "1", ex=ttl)

    def clear_typing(self, session_id: str, user_id: str) -> None:
        self._client().delete(self._typing_key(session_id, user_id))

    def get_typing_users(self, session_id: str) -> list[str]:
        r = self._client()
        prefix = f"{_PREFIX}session:{session_id}:typing:"
        pattern = self._typing_pattern(session_id)
        users: list[str] = []
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor=cursor, match=pattern, count=100)
            for k in keys:
                key_str = k.decode() if isinstance(k, bytes) else k
                users.append(key_str[len(prefix):])
            if cursor == 0:
                break
        return users

    # ── Health ──────────────────────────────────────────────────────

    def is_available(self) -> bool:
        try:
            return self._client().ping()
        except RedisError:
            return False
