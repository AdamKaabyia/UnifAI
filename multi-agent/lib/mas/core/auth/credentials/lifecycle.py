"""
TokenLifecycleService — orchestrates get-token and refresh.

Coordinates CredentialService (store) and protocol (auth server).
Each does its own job; this service decides the order.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from mas.core.auth.errors import TokenExpiredError, TokenRefreshError
from .models import StoredCredential, TokenSet, TokenStatus
from .store import CredentialService

if TYPE_CHECKING:
    from mas.core.auth.ports import AuthProtocol

logger = logging.getLogger(__name__)


class TokenLifecycleService:

    def __init__(self, credential_service: CredentialService, protocol: AuthProtocol):
        self._creds = credential_service
        self._protocol = protocol

    def get_valid_token(
        self, user_id: str, server_id: str, config: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        token = self._creds.get_valid_token(user_id, server_id)
        if token:
            return token
        if config:
            return self._try_refresh(user_id, server_id, config)
        return None

    def get_headers(
        self, user_id: str, server_id: str, config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        token = self.get_valid_token(user_id, server_id, config)
        if not token:
            raise TokenExpiredError(f"No valid token for user={user_id} server={server_id}")
        return self._protocol.build_headers(token)

    def force_refresh(
        self, user_id: str, server_id: str, config: Dict[str, Any],
    ) -> str:
        cred = self._creds.get_credential(user_id, server_id)
        if not cred or not cred.refresh_token:
            raise TokenRefreshError("No credential or refresh token to refresh")

        from global_utils.utils.async_bridge import get_async_bridge
        with get_async_bridge() as bridge:
            return bridge.run(self._do_refresh(cred, config))

    def _try_refresh(
        self, user_id: str, server_id: str, config: Dict[str, Any],
    ) -> Optional[str]:
        cred = self._creds.get_credential(user_id, server_id)
        if not cred or not cred.refresh_token:
            return None
        try:
            from global_utils.utils.async_bridge import get_async_bridge
            with get_async_bridge() as bridge:
                return bridge.run(self._do_refresh(cred, config))
        except Exception as exc:
            logger.info("Refresh failed for server=%s: %s", server_id, exc)
            return None

    async def _do_refresh(self, cred: StoredCredential, config: Dict[str, Any]) -> str:
        try:
            new_tokens: TokenSet = await self._protocol.refresh(config, cred.refresh_token)
        except Exception as exc:
            self._creds.update_status(
                cred.user_id, cred.server_identifier, TokenStatus.REFRESH_FAILED,
            )
            raise TokenRefreshError(f"Refresh failed: {exc}") from exc

        updated = StoredCredential(
            id=cred.id,
            user_id=cred.user_id,
            server_identifier=cred.server_identifier,
            access_token=new_tokens.access_token,
            refresh_token=new_tokens.refresh_token or cred.refresh_token,
            token_type=new_tokens.token_type,
            expires_at=new_tokens.expires_at or cred.expires_at,
            scopes=cred.scopes,
            status=TokenStatus.ACTIVE,
        )
        self._creds.save(updated)
        logger.debug("Token refreshed for user=%s server=%s", cred.user_id, cred.server_identifier)
        return updated.access_token
