"""
Auth-layer ports — abstract contracts that define the hexagonal boundary.

:class:`AuthProtocol`  — what any authentication protocol must do.
:class:`LoginContext`   — protocol-agnostic login redirect data.
:class:`HttpClient`     — async HTTP I/O used by protocol adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .credentials.models import TokenSet


class AuthProtocol(ABC):
    """What any authentication protocol must be able to do."""

    @property
    @abstractmethod
    def protocol_type(self) -> str: ...

    @abstractmethod
    async def build_login_context(
        self,
        config: Dict[str, Any],
        redirect_uri: str,
        state: str,
    ) -> LoginContext:
        """Return a URL + metadata the caller needs to redirect the user."""
        ...

    @abstractmethod
    async def exchange_credentials(
        self,
        config: Dict[str, Any],
        code: str,
        code_verifier: Optional[str],
        redirect_uri: str,
    ) -> TokenSet:
        """Turn whatever the provider sent back into tokens."""
        ...

    @abstractmethod
    async def refresh(
        self,
        config: Dict[str, Any],
        refresh_token: str,
    ) -> TokenSet:
        """Get a fresh token set using a refresh artifact."""
        ...

    @abstractmethod
    async def validate_token(
        self,
        access_token: str,
        server_url: str,
    ) -> bool:
        """Check whether *access_token* is accepted by *server_url*.

        Makes a real connection to the server (e.g. a lightweight probe)
        and returns ``True`` if the token is valid, ``False`` otherwise.
        """
        ...

    @abstractmethod
    def build_headers(self, access_token: str) -> Dict[str, str]:
        """Return HTTP headers for an authenticated request."""
        ...


class LoginContext:
    """Protocol-agnostic: what the caller needs to redirect the user."""

    __slots__ = ("url", "state", "code_verifier")

    def __init__(
        self,
        url: str,
        state: str,
        code_verifier: Optional[str] = None,
    ):
        self.url = url
        self.state = state
        self.code_verifier = code_verifier


# ── HTTP I/O port ────────────────────────────────────────────────────

class HttpClient(ABC):

    @abstractmethod
    async def post(
        self,
        url: str,
        *,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ) -> HttpResponse: ...

    @abstractmethod
    async def get(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ) -> HttpResponse: ...


class HttpResponse:
    """Minimal wrapper so domain code is not coupled to httpx.Response."""

    __slots__ = ("status_code", "body", "headers")

    def __init__(
        self,
        status_code: int,
        body: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ):
        self.status_code = status_code
        self.body = body
        self.headers = headers or {}
