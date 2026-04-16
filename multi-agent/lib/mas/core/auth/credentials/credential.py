"""
AuthCredential — the ONLY interface that auth consumers depend on.

MCP providers, RAG providers, webhook tools, and any future element
that needs authenticated HTTP calls depends on this protocol — never
on OAuth 2.x specifics, token stores, or refresh logic.
"""

from __future__ import annotations

from typing import Dict, Protocol, runtime_checkable


@runtime_checkable
class AuthCredential(Protocol):
    """Minimal contract for presenting credentials in HTTP requests."""

    def get_headers(self) -> Dict[str, str]:
        """Return HTTP headers (e.g. ``{"Authorization": "Bearer …"}``)."""
        ...

    def get_token(self) -> str:
        """Return the raw access token string."""
        ...

    def force_refresh(self) -> None:
        """Force a credential refresh (e.g. after a 401)."""
        ...
