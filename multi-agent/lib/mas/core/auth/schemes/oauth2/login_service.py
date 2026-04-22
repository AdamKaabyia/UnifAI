"""
OAuth2LoginService — builds the full login URL for OAuth2.

Combines: scheme.build_login_context + HMAC state + pending store.
Also owns discovery-driven DCR (previously in AuthService).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from mas.core.auth.credentials.ports import ClientConfigStore
from mas.core.auth.credentials.models import ClientConfig

from .models import PendingAuth, PendingStore
from .state_manager import OAuthStateManager

logger = logging.getLogger(__name__)


class OAuth2LoginService:

    def __init__(
        self,
        scheme: "OAuth2Scheme",
        pending_store: PendingStore,
        state_manager: OAuthStateManager,
        callback_url: str,
        client_config_store: Optional[ClientConfigStore] = None,
        detector: Optional[Any] = None,
    ):
        self._scheme = scheme
        self._pending = pending_store
        self._state_mgr = state_manager
        self._callback_url = callback_url
        self._configs = client_config_store
        self._detector = detector

    async def build_login_url(
        self,
        user_id: str,
        server_identifier: str,
        config: Dict[str, Any],
    ) -> Optional[str]:
        """Build a full OAuth2 login URL with PKCE + signed state.

        Also handles auto-registration (DCR) if no client_id is present.
        """
        if not config.get("client_id"):
            config = await self._try_auto_register(
                user_id, server_identifier, config,
            )

        if not config or not config.get("client_id"):
            return None

        state = self._state_mgr.create_state({
            "user_id": user_id,
            "server_identifier": server_identifier,
            "protocol_type": "oauth2",
        })

        try:
            context = await self._scheme.build_login_context(
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

    async def _try_auto_register(
        self,
        user_id: str,
        server_identifier: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Attempt RFC 7591 Dynamic Client Registration."""
        if self._configs:
            existing = self._configs.find_by_server(user_id, server_identifier)
            if existing and existing.client_id:
                return existing.model_dump()

        reg_endpoint = config.get("registration_endpoint")

        if not reg_endpoint and self._detector:
            http_client = getattr(self._detector, '_http_client', None)
            if http_client:
                from .detection import OAuth2DetectionStrategy
                as_meta = await OAuth2DetectionStrategy._fetch_as_metadata(
                    server_identifier, http_client,
                )
                if as_meta:
                    config = {**config, **as_meta}
                    reg_endpoint = config.get("registration_endpoint")

        if not reg_endpoint:
            return config

        redirect_uris = [self._callback_url] if self._callback_url else None
        supported_methods = config.get("token_endpoint_auth_methods_supported", [])
        auth_method = supported_methods[0] if supported_methods else "none"

        try:
            result = await self._scheme.register_client(
                registration_endpoint=reg_endpoint,
                redirect_uris=redirect_uris,
                token_endpoint_auth_method=auth_method,
            )

            client_id = result.get("client_id")
            if not client_id:
                return config

            new_config = {
                **config,
                "client_id": client_id,
                "client_secret": result.get("client_secret"),
                "server_identifier": server_identifier,
            }

            if self._configs:
                self._configs.save(user_id, ClientConfig(
                    client_id=client_id,
                    client_secret=result.get("client_secret"),
                    authorization_endpoint=config.get("authorization_endpoint", ""),
                    token_endpoint=config.get("token_endpoint", ""),
                    token_endpoint_auth_method=auth_method,
                    scopes=config.get("scopes_supported", []),
                    resource_uri=config.get("resource_uri"),
                    server_identifier=server_identifier,
                ))
                logger.info(
                    "Auto-registered OAuth client for server=%s client_id=%s",
                    server_identifier, client_id,
                )

            return new_config

        except Exception as exc:
            logger.warning("Dynamic client registration failed: %s", exc)
            return config
