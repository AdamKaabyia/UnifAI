"""
OAuth2Protocol — the ONE public class in the oauth2 package.

Implements :class:`AuthProtocol` using authlib for all OAuth 2.1 mechanics
(PKCE, authorization URLs, token exchange, refresh).
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client

from mas.core.auth.ports import AuthProtocol, LoginContext
from mas.core.auth.credentials.models import TokenSet
from mas.core.auth.errors import (
    AuthNotConfiguredError,
    ClientRegistrationError,
    TokenEndpointError,
    TokenRefreshError,
)

from .config import OAuth2Config

logger = logging.getLogger(__name__)


class OAuth2Protocol(AuthProtocol):
    """
    OAuth 2.1 — Authorization Code + PKCE.

    All protocol mechanics are delegated to authlib.
    """

    @property
    def protocol_type(self) -> str:
        return "oauth2"

    async def build_login_context(
        self,
        config: Dict[str, Any],
        redirect_uri: str,
        state: str,
    ) -> LoginContext:
        cfg = OAuth2Config.from_dict(config)
        if not cfg.authorization_endpoint:
            raise AuthNotConfiguredError("No authorization_endpoint in config")

        code_verifier = secrets.token_urlsafe(48)

        client = AsyncOAuth2Client(
            client_id=cfg.client_id,
            client_secret=cfg.client_secret,
            code_challenge_method="S256",
        )

        extra: Dict[str, Any] = {}
        if cfg.resource_uri:
            extra["resource"] = cfg.resource_uri
        extra.update(cfg.extra_authorize_params)

        url, _ = client.create_authorization_url(
            cfg.authorization_endpoint,
            state=state,
            redirect_uri=redirect_uri,
            scope=" ".join(cfg.scopes) if cfg.scopes else None,
            code_verifier=code_verifier,
            **extra,
        )
        await client.aclose()

        return LoginContext(url=url, state=state, code_verifier=code_verifier)

    async def exchange_credentials(
        self,
        config: Dict[str, Any],
        code: str,
        code_verifier: Optional[str],
        redirect_uri: str,
    ) -> TokenSet:
        cfg = OAuth2Config.from_dict(config)

        try:
            async with AsyncOAuth2Client(
                client_id=cfg.client_id,
                client_secret=cfg.client_secret,
                token_endpoint_auth_method=cfg.token_endpoint_auth_method,
            ) as client:
                token = await client.fetch_token(
                    cfg.token_endpoint,
                    grant_type="authorization_code",
                    code=code,
                    redirect_uri=redirect_uri,
                    code_verifier=code_verifier,
                )
        except Exception as exc:
            raise TokenEndpointError(f"Code exchange failed: {exc}") from exc

        return _to_token_set(token)

    async def refresh(
        self,
        config: Dict[str, Any],
        refresh_token: str,
    ) -> TokenSet:
        cfg = OAuth2Config.from_dict(config)

        try:
            async with AsyncOAuth2Client(
                client_id=cfg.client_id,
                client_secret=cfg.client_secret,
                token_endpoint_auth_method=cfg.token_endpoint_auth_method,
            ) as client:
                token = await client.fetch_token(
                    cfg.token_endpoint,
                    grant_type="refresh_token",
                    refresh_token=refresh_token,
                )
        except Exception as exc:
            raise TokenRefreshError(f"Refresh failed: {exc}") from exc

        return _to_token_set(token)

    async def validate_token(
        self,
        access_token: str,
        server_url: str,
    ) -> bool:
        """Probe *server_url* with the Bearer token; ``True`` if 2xx."""
        headers = self.build_headers(access_token)
        headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        })
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    server_url,
                    json={
                        "jsonrpc": "2.0", "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "unifai-probe", "version": "1.0"},
                        },
                    },
                    headers=headers,
                )
                return 200 <= resp.status_code < 300
        except Exception as exc:
            logger.debug("Token validation probe failed for %s: %s", server_url, exc)
            return False

    def build_headers(self, access_token: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    async def register_client(
        self,
        registration_endpoint: str,
        client_name: str = "UnifAI",
        redirect_uris: Optional[List[str]] = None,
        token_endpoint_auth_method: str = "none",
    ) -> Dict[str, Any]:
        """RFC 7591 Dynamic Client Registration."""
        body: Dict[str, Any] = {
            "client_name": client_name,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": token_endpoint_auth_method,
        }
        if redirect_uris:
            body["redirect_uris"] = redirect_uris

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    registration_endpoint, json=body,
                    headers={"Accept": "application/json"},
                )
        except Exception as exc:
            raise ClientRegistrationError(f"DCR request failed: {exc}") from exc

        if resp.status_code >= 400:
            try:
                data = resp.json()
                detail = data.get("error_description", data.get("error", ""))
            except Exception:
                detail = resp.text
            raise ClientRegistrationError(
                f"DCR returned {resp.status_code}: {detail}"
            )

        data = resp.json()
        if "client_id" not in data:
            raise ClientRegistrationError("DCR response missing client_id")
        return data


def _to_token_set(token: dict) -> TokenSet:
    """Convert authlib's token dict to our domain TokenSet."""
    expires_at = None
    if "expires_at" in token:
        try:
            expires_at = datetime.fromtimestamp(float(token["expires_at"]), tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            pass
    elif "expires_in" in token:
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(token["expires_in"]))
        except (ValueError, TypeError):
            pass

    return TokenSet(
        access_token=token["access_token"],
        refresh_token=token.get("refresh_token"),
        token_type=token.get("token_type", "Bearer"),
        expires_at=expires_at,
        scope=token.get("scope"),
    )
