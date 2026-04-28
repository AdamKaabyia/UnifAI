"""Sessions API — create, execute, and query workflow sessions."""
from __future__ import annotations

from unifai_cli.api.base import MASClient


class SessionsAPI(MASClient):
    """API methods for workflow sessions."""

    def create_session(self, user_id: str, blueprint_id: str) -> str:
        return self._post("sessions", "user.session.create",
                          json={"blueprintId": blueprint_id, "userId": user_id})

    def submit_session(self, session_id: str, inputs: dict,
                       scope: str = "public", user_id: str = None) -> dict:
        body = {"sessionId": session_id, "inputs": inputs, "scope": scope}
        if user_id:
            body["loggedInUser"] = user_id
        return self._post("sessions", "user.session.submit", json=body)

    def execute_session(self, session_id: str, inputs: dict,
                        stream: bool = False, scope: str = "public"):
        body = {
            "sessionId": session_id,
            "inputs": inputs,
            "stream": stream,
            "scope": scope,
        }
        if stream:
            return self._post_stream("sessions", "user.session.execute", json=body)
        return self._post("sessions", "user.session.execute", json=body)

    def get_session_chat(self, session_id: str) -> dict:
        return self._get("sessions", "session.chat.get",
                         params={"sessionId": session_id})

    def get_session_status(self, session_id: str) -> dict:
        return self._get("sessions", "session.status.get",
                         params={"sessionId": session_id})

    def get_stream_status(self, session_id: str) -> dict:
        return self._get("sessions", "session.stream.status",
                         params={"sessionId": session_id})

    def subscribe_session(self, session_id: str):
        """Subscribe to session events (NDJSON stream)."""
        return self._get_stream("sessions", "session.subscribe",
                                params={"sessionId": session_id})
