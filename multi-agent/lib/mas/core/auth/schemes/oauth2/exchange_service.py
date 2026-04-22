"""
OAuth2ExchangeService — handles the OAuth callback code exchange.

Called by the ``/auth/exchange`` endpoint after the SSO pod
forwards the authorization code.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from mas.core.auth.errors import InvalidStateError, PendingAuthNotFoundError
from mas.core.auth.credentials.models import StoredCredential, TokenStatus
from mas.core.auth.credentials.ports import TokenStore

from .models import PendingStore
from .state_manager import OAuthStateManager

logger = logging.getLogger(__name__)


class OAuth2ExchangeService:

    def __init__(
        self,
        state_manager: OAuthStateManager,
        pending_store: PendingStore,
        token_store: TokenStore,
        scheme: "OAuth2Scheme",
    ):
        self._state_mgr = state_manager
        self._pending = pending_store
        self._tokens = token_store
        self._scheme = scheme

    async def exchange(self, code: str, state: str) -> Dict[str, Any]:
        try:
            payload = self._state_mgr.validate_state(state)
        except ValueError as exc:
            raise InvalidStateError(f"Invalid state: {exc}") from exc

        pending = self._pending.consume(OAuthStateManager.hash_state(state))
        if pending is None:
            raise PendingAuthNotFoundError(
                "No pending auth for this state (already consumed or expired)"
            )

        config = {**pending.extra, "protocol_type": pending.protocol_type}

        token_set = await self._scheme.exchange_credentials(
            config=config,
            code=code,
            code_verifier=pending.code_verifier,
            redirect_uri=pending.redirect_uri,
        )

        self._tokens.upsert(StoredCredential(
            user_id=pending.user_id,
            server_identifier=pending.server_identifier,
            access_token=token_set.access_token,
            refresh_token=token_set.refresh_token,
            token_type=token_set.token_type,
            expires_at=token_set.expires_at,
            scopes=token_set.scope.split() if token_set.scope else [],
            status=TokenStatus.ACTIVE,
            scheme_type="oauth2",
        ))

        logger.info(
            "Token stored for user=%s server=%s",
            pending.user_id, pending.server_identifier,
        )
        return {"success": True, "server_identifier": pending.server_identifier}
