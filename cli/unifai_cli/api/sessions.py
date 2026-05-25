"""Sessions API — create, execute, and query workflow sessions."""
from __future__ import annotations

from unifai_cli.api.base import MASClient


class SessionsAPI(MASClient):
    """API methods for workflow sessions."""

    def _identity_body_fields(self, user_id: Optional[str] = None) -> dict:
        """Fields required by @with_require_identity_authorization on the backend."""
        uid = self._effective_user_id(user_id)
        return {"userId": uid} if uid else {}

    def create_session(self, user_id: str, blueprint_id: str) -> str:
        uid = self._effective_user_id(user_id)
        return self._post(
            "sessions",
            "user.session.create",
            json={"blueprintId": blueprint_id, **self._identity_body_fields(uid)},
            user_id=uid,
        )

    def submit_session(self, session_id: str, inputs: dict,
                       scope: str = "public", user_id: str = None) -> dict:
        uid = self._effective_user_id(user_id)
        body = {
            "sessionId": session_id,
            "inputs": inputs,
            "scope": scope,
            **self._identity_body_fields(uid),
        }
        return self._post("sessions", "user.session.submit", json=body, user_id=uid)

    def execute_session(self, session_id: str, inputs: dict,
                        stream: bool = False, scope: str = "public",
                        user_id: str = None):
        uid = self._effective_user_id(user_id)
        body = {
            "sessionId": session_id,
            "inputs": inputs,
            "stream": stream,
            "scope": scope,
            "streamMode": ["custom"],
            **self._identity_body_fields(uid),
        }
        if stream:
            return self._post_stream(
                "sessions", "user.session.execute", json=body, user_id=uid,
            )
        return self._post("sessions", "user.session.execute", json=body, user_id=uid)

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
