from abc import ABC, abstractmethod
from typing import List, Mapping, Any, Dict, Optional
from datetime import datetime
from mas.session.domain.session_record import SessionRecord
from mas.session.domain.models import SessionChat, TimeSeriesPoint, SystemAnalyticsData
from mas.core.identity import Identity
from mas.core.dto import GroupedCount


class SessionRepository(ABC):
    """
    Abstract persistence API for session records.

    Owner-scoped methods accept an ``Identity`` (user or team) rather than
    a raw ``user_id`` string so that team-owned sessions are properly
    isolated from personal ones.
    """

    @abstractmethod
    def save(self, record: SessionRecord) -> None:
        """Persist a session record (create or update)."""
        ...

    @abstractmethod
    def fetch(self, run_id: str) -> SessionRecord:
        """Load a session record by run_id."""
        ...

    @abstractmethod
    def fetch_chat(self, run_id: str) -> SessionChat:
        """Fetch only messages and output from a session's graph state (projected)."""
        ...

    @abstractmethod
    def list_runs(self, identity: Identity) -> List[str]:
        """Return all run_ids owned by the given identity."""
        ...

    @abstractmethod
    def list_docs(self, identity: Identity) -> List[Mapping[str, Any]]:
        """Return all session documents for an identity in a single query."""
        ...

    @abstractmethod
    def delete(self, run_id: str) -> bool:
        """Delete a session by run_id. Returns True if deleted, False if not found."""
        ...

    @abstractmethod
    def count(self, identity: Identity, filter: Dict[str, Any]) -> int:
        """Count sessions matching filter criteria for an identity."""
        ...
    
    @abstractmethod
    def group_count(
        self,
        identity: Identity,
        group_by: List[str],
        filter: Dict[str, Any] = None
    ) -> List[GroupedCount]:
        """
        Group documents by specified fields and return counts.

        Args:
            identity: The owning identity (user or team) to filter by
            group_by: List of field names to group by
            filter: Optional additional filter criteria

        Returns:
            List of GroupedCount DTOs with grouped field values and count.
        """
        ...

    # ---------- System-wide methods (for admin analytics) ----------

    @abstractmethod
    def count_system(self, since: Optional[datetime] = None) -> int:
        """Count all sessions system-wide (no identity constraint)."""
        ...

    @abstractmethod
    def get_distinct_users(self, since: Optional[datetime] = None) -> List[str]:
        """Get distinct identity IDs from all sessions."""
        ...

    @abstractmethod
    def group_count_system(
        self,
        group_by: List[str],
        since: Optional[datetime] = None
    ) -> List[GroupedCount]:
        """Group all sessions by specified fields and return counts (system-wide)."""
        ...

    @abstractmethod
    def get_session_activity_series(
        self,
        since: Optional[datetime] = None
    ) -> List[TimeSeriesPoint]:
        """
        Get session activity data grouped by appropriate time intervals.

        The implementation determines the appropriate time granularity
        (hourly, daily, monthly) based on the time range.
        """
        ...

    @abstractmethod
    def get_system_analytics(
        self,
        since: Optional[datetime] = None
    ) -> SystemAnalyticsData:
        """
        Get aggregated system analytics data for admin dashboards.

        Returns grouped session data for building user activity and
        top blueprints views.
        """
        ...
