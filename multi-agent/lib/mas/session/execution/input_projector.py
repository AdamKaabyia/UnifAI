"""
Session input projector — stages a user turn into the SessionRecord.

Responsibility (SRP):
  • Map raw external inputs onto GraphState channels
  • Mirror user_prompt into the messages conversation history
  • Derive a human-readable title when missing
  • Transition status to QUEUED
  • Persist the staged record

This runs synchronously at the service boundary — BEFORE any
execution engine (foreground or background) touches the record.
After staging, the UI can immediately read messages from the DB.
"""
from typing import Any, Dict

from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.session.domain.session_record import SessionRecord
from mas.session.domain.status import SessionStatus
from mas.session.management.utils import derive_title
from mas.session.repository.repository import SessionRepository


class SessionInputProjector:
    """
    Stages raw user inputs into a SessionRecord and persists it.

    Stateless — all state lives in the SessionRecord and the repository.
    """

    def __init__(self, repository: SessionRepository) -> None:
        self._repo = repository

    def apply(self, record: SessionRecord, inputs: Dict[str, Any]) -> None:
        """
        Project raw inputs onto the record's graph state, making the
        user turn immediately durable.

        Idempotent with respect to title derivation (skips if already set).
        """
        if record.metadata.title is None:
            if title := derive_title(inputs):
                record.metadata.title = title

        record.graph_state.update(inputs)

        prompt = (inputs.get("user_prompt") or "").strip()
        if prompt:
            record.graph_state.messages.append(
                ChatMessage(role=Role.USER, content=prompt)
            )

        record.status = SessionStatus.QUEUED
        self._repo.save(record)
