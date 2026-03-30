"""
Port (abstract interface) for the collaboration store.

Implementations provide the backing storage for real-time participant
tracking and team-session indexing.  The default implementation uses
Redis; a local in-memory fallback is possible for tests or single-node
deployments.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from .models import Participant, SessionParticipants, TeamSessionIndex


class CollaborationStore(ABC):
    """Transient, real-time collaboration state (not persisted to Mongo)."""

    # ── Participant presence ────────────────────────────────────────

    @abstractmethod
    def add_participant(
        self,
        session_id: str,
        participant: Participant,
        ttl: int = 300,
    ) -> None:
        """Register a participant in a session. TTL (seconds) controls auto-expiry."""
        ...

    @abstractmethod
    def remove_participant(self, session_id: str, user_id: str) -> None:
        """Remove a participant from a session."""
        ...

    @abstractmethod
    def heartbeat(self, session_id: str, user_id: str, ttl: int = 300) -> None:
        """Refresh the presence TTL for a participant."""
        ...

    @abstractmethod
    def get_participants(self, session_id: str) -> SessionParticipants:
        """Get all currently active participants in a session."""
        ...

    # ── Team-session index ──────────────────────────────────────────

    @abstractmethod
    def register_team_session(self, team_id: str, session_id: str) -> None:
        """Add a session to the team's active-session set."""
        ...

    @abstractmethod
    def unregister_team_session(self, team_id: str, session_id: str) -> None:
        """Remove a session from the team's active-session set."""
        ...

    @abstractmethod
    def get_team_sessions(self, team_id: str) -> TeamSessionIndex:
        """List all active sessions for a team."""
        ...

    # ── User-to-sessions mapping ────────────────────────────────────

    @abstractmethod
    def get_user_sessions(self, user_id: str) -> List[str]:
        """List session IDs a user is currently participating in."""
        ...

    # ── Health ──────────────────────────────────────────────────────

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the backing store is reachable."""
        ...
