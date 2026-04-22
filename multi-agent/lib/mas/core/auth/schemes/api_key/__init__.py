"""
API Key scheme implementation.

Static credential — no acquisition flow, no refresh.

Public API:
  - :class:`ApiKeyScheme` — the adapter
"""

from .adapter import ApiKeyScheme

__all__ = ["ApiKeyScheme"]
