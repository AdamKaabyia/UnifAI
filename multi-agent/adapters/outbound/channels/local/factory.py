"""
Local channel factory for same-process execution.

Creates matched writer+reader pairs backed by a shared ``queue.Queue``.
The factory keeps a registry of queues so that ``create()`` and
``create_reader()`` for the same session_id share the same queue.
"""
import queue
from typing import Dict, Optional

from mas.core.channels import ChannelFactory, SessionChannel, SessionChannelReader
from .channel import LocalSessionChannel, LocalSessionChannelReader


class LocalChannelFactory(ChannelFactory):

    def __init__(self) -> None:
        self._queues: Dict[str, queue.Queue] = {}

    def _get_or_create_queue(self, session_id: str) -> queue.Queue:
        if session_id not in self._queues:
            self._queues[session_id] = queue.Queue()
        return self._queues[session_id]

    def create(self, session_id: str) -> SessionChannel:
        q = self._get_or_create_queue(session_id)
        return LocalSessionChannel(session_id=session_id, event_queue=q)

    def create_reader(self, session_id: str) -> Optional[SessionChannelReader]:
        q = self._get_or_create_queue(session_id)
        return LocalSessionChannelReader(session_id=session_id, event_queue=q)
