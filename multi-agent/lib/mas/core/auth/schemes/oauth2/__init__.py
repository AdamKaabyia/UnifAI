"""
OAuth 2.1 strategy implementation.

Handles:
  - Authorization Code + PKCE (S256)
  - Token exchange and refresh
  - RFC 9728 Protected Resource Metadata discovery
  - RFC 7591 Dynamic Client Registration
  - OAuth Authorization Server Metadata (.well-known)

Public API:
  - :class:`OAuth2Strategy` — the self-contained strategy
"""

from .adapter import OAuth2Strategy

__all__ = ["OAuth2Strategy"]
