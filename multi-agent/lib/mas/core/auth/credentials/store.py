"""
CredentialService — CRUD for stored credentials.

Single responsibility: read/write tokens from the store.
Does NOT know about protocols, refresh logic, or auth servers.
"""

from __future__ import annotations

from typing import Optional

from .models import StoredCredential, TokenStatus
from .ports import TokenStore


class CredentialService:

    def __init__(self, token_store: TokenStore):
        self._store = token_store

    def get_credential(self, user_id: str, server_identifier: str) -> Optional[StoredCredential]:
        if not user_id or not server_identifier:
            return None
        return self._store.find_by_server(user_id, server_identifier)

    def get_valid_token(self, user_id: str, server_identifier: str) -> Optional[str]:
        cred = self.get_credential(user_id, server_identifier)
        if cred and cred.is_valid():
            return cred.access_token
        return None

    def save(self, credential: StoredCredential) -> None:
        self._store.upsert(credential)

    def update_status(self, user_id: str, server_identifier: str, status: TokenStatus) -> None:
        cred = self._store.find_by_server(user_id, server_identifier)
        if cred:
            self._store.update_status(cred.user_id, cred.server_identifier, status.value)
