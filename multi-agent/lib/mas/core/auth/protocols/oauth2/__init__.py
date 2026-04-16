"""
OAuth 2.1 protocol implementation.

Handles:
  - Authorization Code + PKCE (S256)
  - Token exchange and refresh
  - RFC 9728 Protected Resource Metadata discovery
  - RFC 7591 Dynamic Client Registration
  - OAuth Authorization Server Metadata (.well-known)

Public API:
  - :class:`OAuth2Protocol` — the adapter (the only public class)
"""

from .adapter import OAuth2Protocol

__all__ = ["OAuth2Protocol"]
