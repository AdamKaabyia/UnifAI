"""
OAuth2LoginService — builds the full login URL for OAuth2.

Combines: protocol.build_login_context + HMAC state + pending store.
The service knows nothing about PKCE or URL parameters — that's the
protocol adapter's job.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from mas.core.auth.ports import AuthProtocol

from .models import PendingAuth, PendingStore
from .state_manager import OAuthStateManager

logger = logging.getLogger(__name__)


class OAuth2LoginService:

    def __init__(
        self,
        protocol: AuthProtocol,
        pending_store: PendingStore,
        state_manager: OAuthStateManager,
        callback_url: str,
    ):
        self._protocol = protocol
        self._pending = pending_store
        self._state_mgr = state_manager
        self._callback_url = callback_url

    async def build_login_url(
        self,
        user_id: str,
        server_identifier: str,
        config: Dict[str, Any],
    ) -> Optional[str]:
        """Build a full OAuth2 login URL with PKCE + signed state."""
        if not config.get("client_id"):
            return None

        state = self._state_mgr.create_state({
            "user_id": user_id,
            "server_identifier": server_identifier,
            "protocol_type": "oauth2",
        })

        try:
            context = await self._protocol.build_login_context(
                config, self._callback_url, state=state,
            )
        except Exception as exc:
            logger.warning("Failed to build auth URL: %s", exc)
            return None

        self._pending.save(PendingAuth(
            state_hash=OAuthStateManager.hash_state(state),
            user_id=user_id,
            server_identifier=server_identifier,
            redirect_uri=self._callback_url,
            code_verifier=context.code_verifier or "",
            protocol_type="oauth2",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            extra={k: v for k, v in config.items() if k in (
                "client_id", "client_secret", "token_endpoint",
                "authorization_endpoint", "scopes", "resource_uri",
            )},
        ))

        return context.url
