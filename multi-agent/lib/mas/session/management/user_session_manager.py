from datetime import datetime
from typing import List, Mapping, Any, Dict, Optional
from mas.session.repository.repository import SessionRepository
from mas.session.building.workflow_session_factory import WorkflowSessionFactory
from mas.session.domain.workflow_session import WorkflowSession
from mas.session.domain.session_record import SessionRecord
from mas.core.run_context import RunContext
from mas.core.dto import GroupedCount
from mas.graph.state.graph_state import GraphState
from mas.session.domain.status import SessionStatus
from mas.blueprints.service import BlueprintService
from mas.session.domain.models import SessionMeta, TimeSeriesPoint, SystemAnalyticsData
from mas.session.domain.exceptions import BlueprintNotFoundError


class UserSessionManager:
    """
    High-level CRUD for user sessions.
    SRP: only creates, loads, and lists sessions.
    """

    def __init__(
            self,
            repository: SessionRepository,
            session_factory: WorkflowSessionFactory,
            blueprint_service: BlueprintService,
    ):
        self._repo = repository
        self._factory = session_factory
        self._bp_service = blueprint_service

    def blueprint_exists(self, blueprint_id: str) -> bool:
        """Check if blueprint exists without loading it."""
        return self._bp_service.exists(blueprint_id)

    def get_blueprint_metadata(self, blueprint_id: str) -> Dict[str, Any]:
        """Get blueprint metadata dict, empty dict if not found."""
        if not blueprint_id:
            return {}
        try:
            bp_doc = self._bp_service.get_blueprint_draft_doc(blueprint_id)
            return bp_doc.metadata
        except KeyError:
            return {}

    # ---- Create (lightweight — no graph compilation) ----

    def create_session(
            self,
            user_id: str,
            blueprint_id: str,
            metadata: SessionMeta = None,
    ) -> str:
        """Create a session record and return its run_id."""
        if not self.blueprint_exists(blueprint_id):
            raise BlueprintNotFoundError(blueprint_id)

        session_meta = metadata or SessionMeta()
        ctx = RunContext(
            user_id=user_id,
            engine_name=self._factory.engine_name,
            metadata=session_meta.model_dump(),
        )

        record = SessionRecord(
            run_id=ctx.run_id,
            user_id=user_id,
            blueprint_id=blueprint_id,
            run_context=ctx,
            metadata=session_meta,
            graph_state=GraphState(),
            status=SessionStatus.PENDING,
        )
        self._repo.save(record)
        return record.run_id

    # ---- Read ----

    def get_record(self, run_id: str) -> SessionRecord:
        """Lightweight fetch — returns typed SessionRecord, no graph build."""
        return self._repo.fetch(run_id)

    def get_session(self, run_id: str) -> WorkflowSession:
        """Full build — compiles runtime plan + executable graph from the record."""
        record = self.get_record(run_id)

        if not self.blueprint_exists(record.blueprint_id):
            raise BlueprintNotFoundError(record.blueprint_id, session_id=run_id)

        blueprint_spec = self._bp_service.load_resolved(record.blueprint_id)
        return self._factory.build_session(record, blueprint_spec)

    def list_sessions_ids(self, user_id: str) -> List[str]:
        """All run_ids belonging to this user."""
        return self._repo.list_runs(user_id)

    def list_docs(self, user_id: str) -> List[Mapping[str, Any]]:
        """Raw documents for bulk listing (chat history, etc.)."""
        return self._repo.list_docs(user_id)

    def delete_session(self, run_id: str) -> bool:
        """Delete a session by run_id. Returns True if deleted, False if not found."""
        return self._repo.delete(run_id)

    # ---------- statistics ----------
    def count(self, user_id: str, filter: Dict[str, Any] = None) -> int:
        """Count sessions matching filter criteria for a user."""
        return self._repo.count(user_id, filter or {})

    def group_count(
        self, 
        user_id: str, 
        group_by: List[str],
        filter: Dict[str, Any] = None
    ) -> List[GroupedCount]:
        """
        Group sessions by specified fields and return counts.
        Performs efficient server-side grouping via the repository.
        
        Args:
            user_id: The user ID to filter by
            group_by: List of field names to group by (e.g., ["blueprint_id"])
            filter: Optional additional filter criteria
            
        Returns:
            List of GroupedCount DTOs with grouped field values and count.
        """
        return self._repo.group_count(user_id, group_by, filter)

# ---------- Statistics (system-wide for admin analytics) ----------

    def count_system(self, since: Optional[datetime] = None) -> int:
        """Count all sessions system-wide (no user_id constraint)."""
        return self._repo.count_system(since)

    def get_distinct_users(self, since: Optional[datetime] = None) -> List[str]:
        """Get distinct user IDs from all sessions."""
        return self._repo.get_distinct_users(since)

    def group_count_system(
        self,
        group_by: List[str],
        since: Optional[datetime] = None
    ) -> List[GroupedCount]:
        """Group all sessions by specified fields and return counts (system-wide)."""
        return self._repo.group_count_system(group_by, since)

    def get_session_activity_series(
        self,
        since: Optional[datetime] = None
    ) -> List[TimeSeriesPoint]:
        """Get session activity data grouped by appropriate time intervals."""
        return self._repo.get_session_activity_series(since)

    def get_system_analytics(
        self,
        since: Optional[datetime] = None
    ) -> SystemAnalyticsData:
        """Get aggregated system analytics data for admin dashboards."""
        return self._repo.get_system_analytics(since)