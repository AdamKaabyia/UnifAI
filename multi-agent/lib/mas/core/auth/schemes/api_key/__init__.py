"""
API Key strategy implementation.

Static credential — no acquisition flow, no refresh.

Public API:
  - :class:`ApiKeyStrategy` — the adapter
"""

from .adapter import ApiKeyStrategy

__all__ = ["ApiKeyStrategy"]
