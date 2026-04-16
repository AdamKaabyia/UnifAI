"""
Runtime instance produced by OAuthClientFactory.

Implements :class:`AuthCredential` so any consumer can call
``get_headers()`` without knowing about protocols or stores.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from mas.core.auth.credentials.lifecycle import TokenLifecycleService


class OAuthClientInstance:

    def __init__(
        self,
        lifecycle: Optional[TokenLifecycleService],
        user_id: str,
        server_identifier: str,
        config: Dict[str, Any],
    ):
        self._lifecycle = lifecycle
        self._user_id = user_id
        self._server_id = server_identifier
        self._config = config

    def get_headers(self) -> Dict[str, str]:
        return self._lifecycle.get_headers(self._user_id, self._server_id, self._config)

    def get_token(self) -> str:
        token = self._lifecycle.get_valid_token(self._user_id, self._server_id, self._config)
        if not token:
            from mas.core.auth.errors import TokenExpiredError
            raise TokenExpiredError("No valid token")
        return token

    def force_refresh(self) -> None:
        self._lifecycle.force_refresh(self._user_id, self._server_id, self._config)
