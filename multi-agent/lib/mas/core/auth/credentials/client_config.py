"""
ClientConfigStore — port for storing/retrieving OAuth client credentials.

The auth layer reads client configs (client_id, secret, endpoints) from here.
It doesn't care whether they come from manual setup, DCR, or any other source.
Lookup is by server_identifier only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ClientConfig(BaseModel):
    """Client credentials for an auth server."""
    client_id: str
    client_secret: Optional[str] = None
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    scopes: List[str] = Field(default_factory=list)
    resource_uri: Optional[str] = None
    extra_authorize_params: Dict[str, str] = Field(default_factory=dict)
    protocol_type: str = "oauth2"
    server_identifier: str = ""


class ClientConfigStore(ABC):
    """Port: find client configs by server identifier."""

    @abstractmethod
    def find_by_server(self, user_id: str, server_identifier: str) -> Optional[ClientConfig]: ...

    @abstractmethod
    def save(self, user_id: str, config: ClientConfig) -> None: ...
