"""
Reusable lifecycle handler for background session execution.

Bridges the gap between run_id strings (what workers have) and
SessionRecord objects (what SessionLifecycle needs):
fetch record → call lifecycle transition → close channel.

Uses get_record() (cheap) instead of get_session() (expensive full build)
because lifecycle transitions only need the persistable fields, not
the runtime graph or node instances.

Inputs are already staged into the SessionRecord by SessionInputProjector
before the background worker starts.  This handler only manages the
execution lifecycle: begin → complete | fail.

Adapters (Temporal activities, Celery tasks, etc.) delegate to this
class so they remain thin one-liner wrappers with zero business logic.
"""
from typing import Optional

from mas.core.channels import ChannelFactory
from mas.graph.state.graph_state import GraphState
from mas.session.execution.lifecycle import SessionLifecycle
from mas.session.management.user_session_manager import UserSessionManager


class BackgroundLifecycleHandler:

    def __init__(
        self,
        session_manager: UserSessionManager,
        lifecycle: SessionLifecycle,
        channel_factory: Optional[ChannelFactory] = None,
    ) -> None:
        self._manager = session_manager
        self._lifecycle = lifecycle
        self._channel_factory = channel_factory

    def begin(
        self,
        run_id: str,
        scope: str,
        logged_in_user: str,
    ) -> GraphState:
        """Mark RUNNING, bind context, persist. Return the staged GraphState."""
        record = self._manager.get_record(run_id)
        self._lifecycle.begin(record, scope, logged_in_user)
        return record.graph_state

    def complete(self, run_id: str, final_state: GraphState) -> None:
        record = self._manager.get_record(run_id)
        self._lifecycle.complete(record, final_state)
        self._close_channel(run_id)

    def fail(self, run_id: str, error_message: str) -> None:
        record = self._manager.get_record(run_id)
        self._lifecycle.fail(record, RuntimeError(error_message))
        self._close_channel(run_id)

    def _close_channel(self, session_id: str) -> None:
        if self._channel_factory:
            channel = self._channel_factory.create(session_id)
            channel.close()
