"""
Auth-layer ports — abstract contracts that define the hexagonal boundary.

:class:`AuthScheme`            — what ANY auth mechanism must do.
:class:`InteractiveAuthScheme` — schemes that also have a user-facing acquisition flow.
:class:`LoginContext`          — protocol-agnostic login redirect data.
:class:`HttpClient`            — async HTTP I/O used by scheme adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .credentials.models import StoredCredential, TokenSet, RecoveryResult


class AuthScheme(ABC):
    """What any authentication scheme must be able to do."""

    @property
    @abstractmethod
    def scheme_type(self) -> str: ...

    @abstractmethod
    def build_headers(self, credential: StoredCredential) -> Dict[str, str]:
        """Return HTTP headers for an authenticated request."""
        ...

    @abstractmethod
    async def validate(self, credential: StoredCredential, server_url: str) -> bool:
        """Probe *server_url* with the credential; ``True`` if accepted."""
        ...

    @abstractmethod
    async def attempt_recovery(
        self,
        credential: StoredCredential,
        config: Dict[str, Any],
    ) -> RecoveryResult:
        """The credential was rejected. Try to self-heal.

        For OAuth: attempt a token refresh.
        For API key: return not-recoverable.
        """
        ...


class InteractiveAuthScheme(AuthScheme):
    """Schemes that require a multi-step user-facing acquisition flow."""

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


class LoginContext:
    """What the caller needs to redirect the user."""

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
