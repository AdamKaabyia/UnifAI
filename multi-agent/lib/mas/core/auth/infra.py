"""
AuthInfra — bundle of auth ports for injection via ElementDeps.

Used at session build time to create credential instances for auth elements.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .ports import AuthProtocol
from .credentials.ports import TokenStore
from .credentials.client_config import ClientConfigStore


@dataclass(frozen=True)
class AuthInfra:
    """Immutable bundle passed through :class:`ElementDeps`."""
    token_store: TokenStore
    protocol: AuthProtocol
    client_config_store: Optional[ClientConfigStore] = None
