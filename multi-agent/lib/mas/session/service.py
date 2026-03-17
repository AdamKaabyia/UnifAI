from typing import Any, Dict, List, Optional
from datetime import datetime
from mas.session.management.user_session_manager import UserSessionManager
from mas.session.execution.foreground_runner import ForegroundSessionRunner
from mas.session.execution.input_projector import SessionInputProjector
from mas.session.execution.ports import BackgroundSessionSubmitter, SubmitSessionRequest
from mas.session.domain.workflow_session import WorkflowSession
from mas.session.domain.session_record import SessionRecord
from mas.session.domain.dto import ChatHistoryItem
from mas.session.domain.models import SessionMeta, TimeSeriesPoint, SystemAnalyticsData
from mas.session.domain.exceptions import BlueprintNotFoundError
from mas.core.dto import GroupedCount

class SessionService:
    """
    Application use-case boundary for session lifecycle.

    Every entry point (run / stream / submit) follows the same two-phase pattern:
      1. STAGE  — project inputs onto the record and persist (via projector)
      2. EXECUTE — hydrate session and run the graph (foreground or background)
    """

    def __init__(
        self,
        manager: UserSessionManager,
        foreground_runner: ForegroundSessionRunner,
        input_projector: SessionInputProjector,
        background_submitter: Optional[BackgroundSessionSubmitter] = None,
    ):
        self._manager = manager
        self._foreground = foreground_runner
        self._projector = input_projector
        self._submitter = background_submitter

    def create(self, user_id: str, blueprint_id: str, metadata: Dict[str, Any] | SessionMeta | None = None) -> str:
        """
        Create a new session record and return its run_id.
        Lightweight — no graph compilation or blueprint resolution.
        """
        return self._manager.create_session(
            user_id=user_id,
            blueprint_id=blueprint_id,
            metadata=SessionMeta.model_validate(metadata or {}),
        )

    # ---- Two-phase execution entry points ----

    def run(
        self,
        session_id: str,
        inputs: Dict[str, Any],
        scope: str = "public",
        logged_in_user: str = "",
        stream: bool = False,
    ) -> Any:
        """
        Execute the session graph.

        When *stream* is False, blocks until completion and returns the
        final ``GraphState``.

        When *stream* is True, returns an ``Iterator`` of channel events.
        The execution runs on a background thread; lifecycle transitions
        are handled internally by the runner.
        """
        self._stage(session_id, inputs)
        session = self._manager.get_session(session_id)
        return self._foreground.run(
            session=session,
            scope=scope,
            logged_in_user=logged_in_user,
            stream=stream,
        )

    def submit(self, session_id: str, inputs: Dict[str, Any],
               scope: str = "public", logged_in_user: str = "") -> str:
        """
        Non-blocking submit: stage inputs, then start a background workflow
        and return its handle/ID immediately (HTTP 202 pattern).
        """
        if self._submitter is None:
            raise TypeError(
                "No BackgroundSessionSubmitter configured — "
                "submit() is not available for this engine."
            )
        self._stage(session_id, inputs)
        session = self._manager.get_session(session_id)
        request = SubmitSessionRequest(
            scope=scope,
            logged_in_user=logged_in_user,
        )
        return self._submitter.submit(session, request)

    # ---- Private staging ----

    def _stage(self, session_id: str, inputs: Dict[str, Any]) -> None:
        """Project raw inputs onto the record and persist (QUEUED)."""
        record = self._manager.get_record(session_id)
        self._projector.apply(record, inputs or {})

    def list_for_user(self, user_id: str) -> list:
        """
        List all sessions created by a user.
        """
        return self._manager.list_sessions_ids(user_id)

    def get(self, run_id: str) -> WorkflowSession:
        """
        Fetch a fully hydrated session by its run_id.
        """
        return self._manager.get_session(run_id)

    def get_record(self, run_id: str) -> SessionRecord:
        """
        Fetch a lightweight session record (no graph build).
        """
        return self._manager.get_record(run_id)

    def get_status(self, run_id: str) -> str:
        """
        Get the status of a session by its run_id.
        """
        record = self._manager.get_record(run_id)
        return record.status.name

    def get_state(self, run_id: str) -> Dict[str, Any]:
        """
        Get the graph state of a session by its run_id.
        """
        record = self._manager.get_record(run_id)
        return record.graph_state.model_dump(mode="json")

    def get_user_sessions_chat_history(self, user_id: str) -> list:
        """
        Get chat history for all sessions created by a user.
        """
        docs = self._manager.list_docs(user_id)
        chat_items = []

        for doc in docs:
            blueprint_id = doc.get("blueprint_id", "")
            blueprint_exists = self._manager.blueprint_exists(blueprint_id) if blueprint_id else False
            bp_metadata = self._manager.get_blueprint_metadata(blueprint_id) if blueprint_exists else {}

            public_usage_scope = False
            if blueprint_exists and blueprint_id:
                source = doc.get("metadata", {}).get("source", "")
                if source == "public_link":
                    public_usage_scope = bp_metadata.get("usageScope") == "public"

            chat_item = ChatHistoryItem.from_doc(doc, blueprint_exists=blueprint_exists, public_usage_scope=public_usage_scope, blueprint_metadata=bp_metadata)
            chat_items.append(chat_item.model_dump())

        return chat_items

    def get_user_blueprints(self, user_id) -> List[str]:
        """
        Get all blueprints created by a user.
        """
        docs = self._manager.list_docs(user_id)
        return list({d.get("blueprint_id") for d in docs})

    def group_count(
        self,
        user_id: str,
        group_by: List[str],
        filter: Dict[str, Any] = None
    ) -> List[GroupedCount]:
        """
        Group sessions by specified fields and return counts.
        Performs efficient server-side grouping via the session manager.
        """
        return self._manager.group_count(user_id, group_by, filter)

    def count(self, user_id: str, filter: Dict[str, Any] = None) -> int:
        """Count sessions matching filter criteria for a user."""
        return self._manager.count(user_id, filter)

    def delete(self, run_id: str) -> bool:
        """
        Delete a session by run_id. Returns True if deleted, False if not found.
        """
        return self._manager.delete_session(run_id)

# ---------- System-wide methods (for admin analytics) ----------

    def count_system(self, since: Optional[datetime] = None) -> int:
        """
        Count all sessions system-wide (no user_id constraint).
        """
        return self._manager.count_system(since)

    def get_distinct_users(self, since: Optional[datetime] = None) -> List[str]:
        """
        Get distinct user IDs from all sessions.
        """
        return self._manager.get_distinct_users(since)

    def group_count_system(
        self,
        group_by: List[str],
        since: Optional[datetime] = None
    ) -> List[GroupedCount]:
        """
        Group all sessions by specified fields and return counts (system-wide).
        No user_id constraint — for admin analytics.
        """
        return self._manager.group_count_system(group_by, since)

    def get_session_activity_series(
        self,
        since: Optional[datetime] = None
    ) -> List[TimeSeriesPoint]:
        """
        Get session activity data grouped by appropriate time intervals.
        For admin analytics dashboards.
        """
        return self._manager.get_session_activity_series(since)

    def get_system_analytics(
        self,
        since: Optional[datetime] = None
    ) -> SystemAnalyticsData:
        """
        Get aggregated system analytics data for admin dashboards.
        """
        return self._manager.get_system_analytics(since)
