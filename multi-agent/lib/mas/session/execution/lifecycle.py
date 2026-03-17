"""
Session lifecycle state-machine transitions.

Operates on SessionRecord (the persistable layer) so that both foreground
runners and background workers can share the same logic without requiring
a full WorkflowSession.

Input staging (projecting raw inputs onto GraphState) is NOT this class's
job — that belongs to SessionInputProjector.  This class only manages
execution state transitions: begin → complete | fail.
"""
from mas.graph.state.graph_state import GraphState
from mas.session.repository.repository import SessionRepository
from mas.session.domain.session_record import SessionRecord
from mas.session.domain.status import SessionStatus
from mas.core.context import set_current_context


class SessionLifecycle:
    """
    Owns the begin / complete / fail transitions of a SessionRecord.

    Stateless — all state lives in the SessionRecord and the repository.
    """

    def __init__(self, repository: SessionRepository) -> None:
        self._repo = repository

    def begin(
        self,
        record: SessionRecord,
        scope: str,
        logged_in_user: str,
    ) -> None:
        """
        Start execution: bind run context, mark RUNNING, persist.

        Called AFTER inputs have already been staged by SessionInputProjector.
        """
        ctx = record.run_context.change_scope(scope)
        ctx = ctx.set_logged_in_user(logged_in_user)
        set_current_context(ctx)
        record.run_context = ctx

        record.status = SessionStatus.RUNNING
        self._repo.save(record)

    def complete(
        self,
        record: SessionRecord,
        final_state: GraphState,
    ) -> None:
        """
        Post-execution: attach final state, mark COMPLETED, persist.
        """
        record.graph_state = final_state
        record.run_context = record.run_context.mark_finished()
        set_current_context(record.run_context)
        record.status = SessionStatus.COMPLETED
        self._repo.save(record)

    def fail(
        self,
        record: SessionRecord,
        error: Exception,
    ) -> None:
        """
        On error: mark FAILED, persist.
        """
        record.run_context = record.run_context.mark_finished()
        record.status = SessionStatus.FAILED
        self._repo.save(record)
