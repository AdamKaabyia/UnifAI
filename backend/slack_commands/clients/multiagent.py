"""Outbound adapter — HTTP client for the Multi-Agent service.

Encapsulates all network I/O to multi-agent so that command handlers
remain pure application logic with no HTTP coupling.
"""
import logging
from dataclasses import dataclass
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 10


@dataclass(frozen=True)
class BlueprintSummary:
    blueprint_id: str
    name: str
    description: str = ""


class MultiagentClient:
    """Typed HTTP client for the multi-agent platform API."""

    def __init__(self, base_url: str, timeout: int = _DEFAULT_TIMEOUT):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def list_sessions(self, user_name: str) -> List[dict]:
        resp = requests.get(
            f"{self._base_url}/api/sessions/session.user.list",
            params={"userId": user_name, "identityType": "user"},
            headers=self._auth_headers(user_name),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def list_blueprints(self, user_name: str) -> List[BlueprintSummary]:
        resp = requests.get(
            f"{self._base_url}/api/blueprints/available.blueprints.summary.get",
            params={"userId": user_name, "identityType": "user"},
            headers=self._auth_headers(user_name),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        raw = resp.json()
        return [
            BlueprintSummary(
                blueprint_id=bp.get("blueprint_id", ""),
                name=bp.get("name") or bp.get("spec_dict", {}).get("name") or "",
                description=bp.get("description") or "",
            )
            for bp in raw
        ]

    def session_exists(self, session_id: str, user_name: str) -> bool:
        try:
            resp = requests.get(
                f"{self._base_url}/api/sessions/session.status.get",
                params={"sessionId": session_id},
                headers=self._auth_headers(user_name),
                timeout=5,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def create_session(self, user_name: str, blueprint_id: str) -> str:
        resp = requests.post(
            f"{self._base_url}/api/sessions/user.session.create",
            json={
                "blueprintId": blueprint_id,
                "userId": user_name,
                "identityType": "user",
            },
            headers=self._content_headers(user_name),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def submit_session(self, user_name: str, session_id: str, prompt: str) -> None:
        resp = requests.post(
            f"{self._base_url}/api/sessions/user.session.submit",
            json={
                "sessionId": session_id,
                "inputs": {"user_prompt": prompt},
                "userId": user_name,
                "identityType": "user",
            },
            headers=self._content_headers(user_name),
            timeout=15,
        )
        resp.raise_for_status()

    def get_session_status(self, session_id: str, user_name: str) -> Optional[str]:
        resp = requests.get(
            f"{self._base_url}/api/sessions/session.status.get",
            params={"sessionId": session_id},
            headers=self._auth_headers(user_name),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        status = resp.json()
        return status.upper() if isinstance(status, str) else None

    def get_session_state(self, session_id: str, user_name: str) -> dict:
        resp = requests.get(
            f"{self._base_url}/api/sessions/session.state.get",
            params={"sessionId": session_id},
            headers=self._auth_headers(user_name),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def cancel_session(self, session_id: str, user_name: str) -> bool:
        """Cancel a running session. Returns True if cancelled, False if not cancellable."""
        resp = requests.post(
            f"{self._base_url}/api/sessions/session.cancel",
            json={"sessionId": session_id},
            headers=self._content_headers(user_name),
            timeout=self._timeout,
        )
        if resp.status_code == 409:
            return False
        resp.raise_for_status()
        return True

    def delete_session(self, session_id: str, user_name: str) -> bool:
        """Delete a session. Returns True if deleted, False if not found."""
        resp = requests.delete(
            f"{self._base_url}/api/sessions/session.delete",
            params={"sessionId": session_id},
            headers=self._auth_headers(user_name),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json().get("success", False)

    def get_session_chat(self, session_id: str, user_name: str) -> dict:
        """Fetch the chat messages for a session."""
        resp = requests.get(
            f"{self._base_url}/api/sessions/session.chat.get",
            params={"sessionId": session_id},
            headers=self._auth_headers(user_name),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def get_session_meta(self, session_id: str, user_name: str) -> dict:
        """Fetch the metadata for a session."""
        resp = requests.get(
            f"{self._base_url}/api/sessions/session.meta",
            params={"sessionId": session_id},
            headers=self._auth_headers(user_name),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _auth_headers(self, user_name: str) -> dict:
        return {"X-Authenticated-User": user_name}

    def _content_headers(self, user_name: str) -> dict:
        return {
            "X-Authenticated-User": user_name,
            "Content-Type": "application/json",
        }
