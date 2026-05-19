"""
Self-contained Identity directory HTTP client.

Delegates user/group lookups to the Identity service (``/api/directory/*``).
Uses lightweight local models so multi-agent does not import Identity packages.

TODO: Long-term, this logic should live in the Identity pod, which would expose
internal proxy endpoints (e.g. ``/internal/directory/*``) that MAS calls.
MAS would then hold only a thin HTTP client with no knowledge of RBAC internals.
Kept here for now until a unified backend layer is in place.
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Optional

import requests
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── lightweight directory models ──────────────────────────────────────

class DirectoryUser(BaseModel):
    user_id: str
    username: str
    display_name: str
    email: str = ""
    title: str = ""


class DirectoryGroup(BaseModel):
    group_id: str
    name: str
    description: str = ""
    members: List[str] = Field(default_factory=list)


class DirectoryProvider(ABC):
    """Minimal port for an external user/group directory."""

    def set_user_token(self, token: str) -> None:
        pass

    @abstractmethod
    def search_users(self, query: str, limit: int = 20) -> List[DirectoryUser]: ...

    @abstractmethod
    def get_user(self, user_id: str) -> Optional[DirectoryUser]: ...

    def search_groups(self, query: str, limit: int = 20) -> List[DirectoryGroup]:
        return []

    def get_group(self, group_id: str) -> Optional[DirectoryGroup]:
        return None


# ── Identity HTTP client ──────────────────────────────────────────────

class IdentityDirectoryClient(DirectoryProvider):
    """Talks to the Identity service ``/api/directory/*`` endpoints."""

    def __init__(self, base_url: str, timeout: int = 10):
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._user_token: Optional[str] = None
        logger.info("Identity directory client: %s", self._base)

    def set_user_token(self, token: str) -> None:
        self._user_token = token

    def _headers(self) -> dict:
        h: dict = {}
        if self._user_token:
            h["X-User-Token"] = self._user_token
        return h

    def search_users(self, query: str, limit: int = 20) -> List[DirectoryUser]:
        try:
            resp = requests.get(
                f"{self._base}/api/directory/directory.search_users",
                params={"q": query, "limit": limit},
                headers=self._headers(),
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return [DirectoryUser(**u) for u in resp.json().get("users", [])]
        except Exception:
            logger.exception("SSO directory search_users failed")
            return []

    def get_user(self, user_id: str) -> Optional[DirectoryUser]:
        try:
            resp = requests.get(
                f"{self._base}/api/directory/directory.get_user",
                params={"userId": user_id},
                headers=self._headers(),
                timeout=self._timeout,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return DirectoryUser(**resp.json())
        except Exception:
            logger.exception("SSO directory get_user failed")
            return None

    def search_groups(self, query: str, limit: int = 20) -> List[DirectoryGroup]:
        try:
            resp = requests.get(
                f"{self._base}/api/directory/directory.search_groups",
                params={"q": query, "limit": limit},
                headers=self._headers(),
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return [DirectoryGroup(**g) for g in resp.json().get("groups", [])]
        except Exception:
            logger.exception("SSO directory search_groups failed")
            return []

    def get_group(self, group_id: str) -> Optional[DirectoryGroup]:
        try:
            resp = requests.get(
                f"{self._base}/api/directory/directory.get_group",
                params={"groupId": group_id},
                headers=self._headers(),
                timeout=self._timeout,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return DirectoryGroup(**resp.json())
        except Exception:
            logger.exception("SSO directory get_group failed")
            return None
