"""
Outbound ports for session execution.

Ports are defined by the use-case owner (session layer) and implemented
by infrastructure adapters (Temporal, Celery, etc.).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from mas.session.domain.workflow_session import WorkflowSession
from mas.core.execution_context import ExecutionContext


@dataclass(frozen=True)
class SubmitSessionRequest:
    """Immutable value object carrying execution context for a background worker.

    Inputs are already staged into the SessionRecord before submission,
    so this only carries the execution context (scope, user, etc.).
    """
    execution_context: ExecutionContext = field(default_factory=ExecutionContext)


class BackgroundSessionSubmitter(ABC):
    """
    Outbound port for fire-and-forget session submission.

    Each adapter (Temporal, Celery, RQ, …) implements this port.
    The adapter is responsible for the full session lifecycle
    (prepare → execute → complete/fail) inside its background worker.

    Returns a handle/ID the caller can use for polling.
    """

    @abstractmethod
    def submit(self, session: WorkflowSession, request: SubmitSessionRequest) -> str:
        """
        Submit the session for background execution.

        Returns:
            A workflow/task handle that the caller can use for status polling.
        """
        ...
