"""
Collaboration service — domain logic for multi-user session participation.

Orchestrates participant tracking, team-session indexing, and ensures
that Temporal-backed sessions can be shared across team members through
the existing Redis Streams channel infrastructure.
"""
import logging
from typing import Dict, List, Optional, Tuple

from mas.core.identity import Identity, IdentityType
from mas.session.domain.session_record import SessionRecord
from mas.session.repository.repository import SessionRepository
from .models import (
    Participant,
    ParticipantRole,
    SessionParticipants,
    TeamEditLockHolder,
    TeamSessionIndex,
)
from .ports import CollaborationStore

logger = logging.getLogger(__name__)


class CollaborationService:
    """
    Application-level facade for session collaboration.

    Coordinates between:
    - ``CollaborationStore`` (Redis) for transient participant presence
    - ``SessionRepository`` (Mongo) for persistent ownership checks
    - Existing Redis Streams channel for real-time event delivery
    """

    def __init__(
        self,
        store: CollaborationStore,
        session_repo: SessionRepository,
        presence_ttl: int = 300,
        edit_lock_ttl: int = 180,
        typing_ttl: int = 5,
    ):
        self._store = store
        self._session_repo = session_repo
        self._presence_ttl = presence_ttl
        self._edit_lock_ttl = edit_lock_ttl
        self._typing_ttl = typing_ttl

    # ── Join / Leave ────────────────────────────────────────────────

    def join_session(
        self,
        session_id: str,
        user_id: str,
        display_name: str = "",
        role: ParticipantRole = ParticipantRole.COLLABORATOR,
    ) -> SessionParticipants:
        """
        Add a user to a session's participant list.

        If the session is team-owned, the session is also registered
        in the team's active-session index.

        Returns the updated participant list.
        """
        record = self._session_repo.fetch(session_id)

        if record.identity.id == user_id:
            role = ParticipantRole.OWNER

        participant = Participant(
            user_id=user_id,
            display_name=display_name or user_id,
            role=role,
        )
        self._store.add_participant(session_id, participant, ttl=self._presence_ttl)

        if record.identity.type == IdentityType.TEAM:
            self._store.register_team_session(record.identity.id, session_id)

        participants = self._store.get_participants(session_id)
        self._reconcile_team_session_index_if_empty(session_id, record, participants)
        return participants

    def leave_session(self, session_id: str, user_id: str) -> None:
        """Remove a user from a session's participant list."""
        self._store.remove_participant(session_id, user_id)

        participants = self._store.get_participants(session_id)
        try:
            record = self._session_repo.fetch(session_id)
        except KeyError:
            record = None
        if record is not None:
            self._reconcile_team_session_index_if_empty(session_id, record, participants)

    def heartbeat(self, session_id: str, user_id: str) -> None:
        """Refresh presence TTL for a user in a session."""
        self._store.heartbeat(session_id, user_id, ttl=self._presence_ttl)

    # ── Queries ─────────────────────────────────────────────────────

    def get_participants(self, session_id: str) -> SessionParticipants:
        """Return live participants; drop stale team-session index when everyone TTL'd out."""
        participants = self._store.get_participants(session_id)
        try:
            record = self._session_repo.fetch(session_id)
        except KeyError:
            return participants
        self._reconcile_team_session_index_if_empty(session_id, record, participants)
        return participants

    def _reconcile_team_session_index_if_empty(
        self,
        session_id: str,
        record: SessionRecord,
        participants: SessionParticipants,
    ) -> None:
        if record.identity.type != IdentityType.TEAM:
            return
        if participants.participants:
            return
        self._store.unregister_team_session(record.identity.id, session_id)

    def get_team_sessions(self, team_id: str) -> TeamSessionIndex:
        return self._store.get_team_sessions(team_id)

    def get_user_active_sessions(self, user_id: str) -> List[str]:
        """Sessions the user is currently participating in (across all teams)."""
        return self._store.get_user_sessions(user_id)

    # ── Typing ──────────────────────────────────────────────────────

    def set_typing(self, session_id: str, user_id: str) -> None:
        self._store.set_typing(session_id, user_id, ttl=self._typing_ttl)

    def clear_typing(self, session_id: str, user_id: str) -> None:
        self._store.clear_typing(session_id, user_id)

    def get_typing_users(self, session_id: str) -> list[str]:
        return self._store.get_typing_users(session_id)

    def is_available(self) -> bool:
        return self._store.is_available()

    # ── Team edit locks ─────────────────────────────────────────────

    def acquire_team_edit_lock(
        self,
        team_id: str,
        entity_kind: str,
        entity_id: str,
        user_id: str,
        display_name: str = "",
    ) -> Tuple[bool, Optional[TeamEditLockHolder]]:
        return self._store.acquire_team_edit_lock(
            team_id,
            entity_kind,
            entity_id,
            user_id,
            display_name,
            ttl=self._edit_lock_ttl,
        )

    def release_team_edit_lock(
        self,
        team_id: str,
        entity_kind: str,
        entity_id: str,
        user_id: str,
    ) -> None:
        self._store.release_team_edit_lock(
            team_id, entity_kind, entity_id, user_id
        )

    def renew_team_edit_lock(
        self,
        team_id: str,
        entity_kind: str,
        entity_id: str,
        user_id: str,
        display_name: str = "",
    ) -> bool:
        return self._store.renew_team_edit_lock(
            team_id,
            entity_kind,
            entity_id,
            user_id,
            display_name,
            ttl=self._edit_lock_ttl,
        )

    def get_team_edit_lock(
        self,
        team_id: str,
        entity_kind: str,
        entity_id: str,
    ) -> Optional[TeamEditLockHolder]:
        return self._store.get_team_edit_lock(team_id, entity_kind, entity_id)

    def get_team_edit_locks_batch(
        self,
        team_id: str,
        entity_kind: str,
        entity_ids: list[str],
    ) -> Dict[str, Optional[TeamEditLockHolder]]:
        return self._store.get_team_edit_locks_batch(
            team_id, entity_kind, entity_ids
        )
