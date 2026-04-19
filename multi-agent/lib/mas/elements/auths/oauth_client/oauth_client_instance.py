"""
Runtime instance produced by OAuthClientFactory.

Implements :class:`AuthCredential` so any consumer can call
``get_headers()`` without knowing about protocols or stores.

NOTE: This is now a thin wrapper around BoundCredential for backward
compatibility with OAuthClientFactory's fallback (no-credential) path.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from mas.core.auth.service import AuthService, BoundCredential


class OAuthClientInstance:

    def __init__(
        self,
        auth_service: Optional[AuthService] = None,
        user_id: str = "",
        server_identifier: str = "",
        config: Optional[Dict[str, Any]] = None,
    ):
        if auth_service and user_id and server_identifier:
            self._delegate = BoundCredential(
                auth_service=auth_service,
                user_id=user_id,
                server_identifier=server_identifier,
                config=config,
            )
        else:
            self._delegate = None

    def get_headers(self) -> Dict[str, str]:
        if not self._delegate:
            return {}
        return self._delegate.get_headers()

    def get_token(self) -> str:
        if not self._delegate:
            from mas.core.auth.errors import TokenExpiredError
            raise TokenExpiredError("No auth service configured")
        return self._delegate.get_token()

    def force_refresh(self) -> None:
        if self._delegate:
            self._delegate.force_refresh()
