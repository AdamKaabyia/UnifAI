"""
OAuth2Protocol — the ONE public class in the oauth2 package.

Implements :class:`AuthProtocol`.  All OAuth2-specific mechanics are
delegated to private modules (_pkce, _url_builder, _token_handler, …).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mas.core.auth.ports import AuthProtocol, HttpClient, LoginContext
from mas.core.auth.credentials.models import TokenSet

from .config import OAuth2Config
from ._pkce import generate_pkce_pair
from ._url_builder import build_authorization_url
from ._token_handler import exchange_code, refresh_token_set
from ._client_registrar import register_client


class OAuth2Protocol(AuthProtocol):
    """
    OAuth 2.1 — Authorization Code + PKCE.

    All HTTP I/O is delegated to :class:`HttpClient` (port).
    """

    def __init__(self, http_client: HttpClient):
        self._http = http_client

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
        pkce = generate_pkce_pair()
        url = build_authorization_url(
            cfg=cfg, redirect_uri=redirect_uri, state=state, pkce=pkce,
        )
        return LoginContext(url=url, state=state, code_verifier=pkce.verifier)

    async def exchange_credentials(
        self,
        config: Dict[str, Any],
        code: str,
        code_verifier: Optional[str],
        redirect_uri: str,
    ) -> TokenSet:
        cfg = OAuth2Config.from_dict(config)
        return await exchange_code(
            http=self._http, cfg=cfg, code=code,
            code_verifier=code_verifier, redirect_uri=redirect_uri,
        )

    async def refresh(
        self,
        config: Dict[str, Any],
        refresh_token: str,
    ) -> TokenSet:
        cfg = OAuth2Config.from_dict(config)
        return await refresh_token_set(
            http=self._http, cfg=cfg, refresh_token=refresh_token,
        )

    def build_headers(self, access_token: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    async def register_client(
        self,
        registration_endpoint: str,
        client_name: str = "UnifAI",
        redirect_uris: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return await register_client(
            http=self._http, registration_endpoint=registration_endpoint,
            client_name=client_name, redirect_uris=redirect_uris,
        )
