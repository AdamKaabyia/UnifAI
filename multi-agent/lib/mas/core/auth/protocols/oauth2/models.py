"""
OAuth2-specific flow models.

These only exist because OAuth2 uses redirect-based auth (authorization URLs,
PKCE, pending state). Other protocols (API key, bearer) don't need them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class PendingAuth(BaseModel):
    """Short-lived data stored while waiting for an OAuth callback."""
    state_hash: str
    user_id: str
    server_identifier: str = ""
    redirect_uri: str
    code_verifier: str
    protocol_type: str
    expires_at: datetime
    extra: Dict[str, Any] = Field(default_factory=dict)


class PendingStore(ABC):
    """Short-lived storage for in-flight OAuth handshakes (PKCE state, …)."""

    @abstractmethod
    def save(self, pending: PendingAuth) -> None: ...

    @abstractmethod
    def consume(self, state_hash: str) -> Optional[PendingAuth]:
        """Atomically read-and-delete. Returns ``None`` if not found."""
        ...
