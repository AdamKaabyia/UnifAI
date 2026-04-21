"""
AuthService — single service that owns the full token lifecycle.

Merges the responsibilities of the former CredentialService (CRUD)
and TokenLifecycleService (refresh orchestration) into one place.
Consumers never touch TokenStore or AuthProtocol directly.

Also contains :class:`BoundCredential`, the handle that elements
receive at build time so they can call ``get_headers()`` with no args.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from .errors import TokenExpiredError, TokenRefreshError
from .credentials.models import StoredCredential, TokenSet, TokenStatus, ClientConfig
from .credentials.ports import TokenStore, ClientConfigStore
from .ports import AuthProtocol

if TYPE_CHECKING:
    from .credentials.credential import AuthCredential

logger = logging.getLogger(__name__)


class BoundCredential:
    """Binds AuthService to a specific (user, server) pair.

    Satisfies the :class:`AuthCredential` protocol so elements can call
    ``get_headers()`` / ``get_token()`` / ``force_refresh()`` without
    passing user_id and server_identifier every time.

    Accepts either a plain ``user_id`` string or an
    ``ExecutionContextHolder`` for deferred resolution (session build
    time, when the user context isn't available yet).
    """

    def __init__(
        self,
        auth_service: AuthService,
        user_id: Any,
        server_identifier: str,
        config: Optional[Dict[str, Any]] = None,
    ):
        self._svc = auth_service
        self._user_id_or_holder = user_id
        self._server_id = server_identifier
        self._config = config or {}

    @property
    def _user_id(self) -> str:
        uid = self._user_id_or_holder
        if isinstance(uid, str):
            return uid
        return uid.user_id

    def get_headers(self, *, force_refresh: bool = False) -> Dict[str, str]:
        if force_refresh:
            self._svc.force_refresh(
                self._user_id, self._server_id, self._config,
            )
        return self._svc.get_headers(
            self._user_id, self._server_id, self._config,
        )

    def get_token(self) -> str:
        token = self._svc.get_valid_token(
            self._user_id, self._server_id, self._config,
        )
        if not token:
            raise TokenExpiredError("No valid token")
        return token


class AuthService:

    def __init__(
        self,
        token_store: TokenStore,
        protocol: AuthProtocol,
        client_config_store: Optional[ClientConfigStore] = None,
        detector: Optional[Any] = None,
        login_service: Optional[Any] = None,
    ):
        self._store = token_store
        self._protocol = protocol
        self._configs = client_config_store
        self._detector = detector
        self._login = login_service

    def get_credential(
        self, user_id: str, server_identifier: str,
    ) -> Optional[StoredCredential]:
        if not user_id or not server_identifier:
            return None
        return self._store.find_by_server(user_id, server_identifier)

    def save_credential(self, credential: StoredCredential) -> None:
        self._store.upsert(credential)

    def update_status(
        self, user_id: str, server_identifier: str, status: TokenStatus,
    ) -> None:
        cred = self._store.find_by_server(user_id, server_identifier)
        if cred:
            self._store.update_status(
                cred.user_id, cred.server_identifier, status.value,
            )

    def get_client_config(
        self, user_id: str, server_identifier: str,
    ) -> Optional[ClientConfig]:
        if not self._configs:
            return None
        return self._configs.find_by_server(user_id, server_identifier)

    def get_valid_token(
        self,
        user_id: str,
        server_identifier: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Return a valid access token, refreshing transparently if needed.

        1. Check the store for a locally-valid token.
        2. If expired, resolve config if not provided, then attempt a refresh.
        """
        cred = self.get_credential(user_id, server_identifier)
        if cred:
            from datetime import datetime, timezone
            print(
                "Token check: user=%s server=%s status=%s expires_at=%s now=%s is_valid=%s",
                user_id, server_identifier, cred.status, cred.expires_at,
                datetime.now(timezone.utc), cred.is_valid(),
            )
        if cred and cred.is_valid():
            return cred.access_token
        if cred:
            resolved = config or self._resolve_config(user_id, server_identifier)
            if resolved and resolved.get("token_endpoint"):
                return self._refresh(cred, resolved)
        return None

    def get_headers(
        self,
        user_id: str,
        server_identifier: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        token = self.get_valid_token(user_id, server_identifier, config)
        if not token:
            raise TokenExpiredError(
                f"No valid token for user={user_id} server={server_identifier}"
            )
        return self._protocol.build_headers(token)

    async def is_token_valid(
        self,
        user_id: str,
        server_identifier: str,
        url: str,
    ) -> bool:
        """Real connection check — probe *url* with the stored token.

        Returns ``True`` if the token is accepted, ``False`` if there is
        no credential, the local expiry check fails, or the remote
        server rejects it.
        """
        cred = self.get_credential(user_id, server_identifier)
        if not cred or not cred.is_valid():
            return False
        return await self._protocol.validate_token(cred.access_token, url)

    def force_refresh(
        self,
        user_id: str,
        server_identifier: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        cred = self.get_credential(user_id, server_identifier)
        if not cred or not cred.refresh_token:
            raise TokenRefreshError("No credential or refresh token to refresh")

        resolved_config = config or self._resolve_config(user_id, server_identifier)
        return self._refresh(cred, resolved_config, raise_on_error=True)

    # ── Discovery + Login ─────────────────────────────────────────────

    async def discover(
        self,
        url: str,
        response_headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Any]:
        """Detect auth requirements for *url*. Returns a DetectionResult or None."""
        if not self._detector:
            return None
        return await self._detector.detect(url, response_headers)

    async def build_login_url(
        self,
        user_id: str,
        server_identifier: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Build an OAuth login URL for the given user + server.

        1. Check client_configs for an existing client_id.
        2. If none, run discovery to find the registration_endpoint.
        3. If available, auto-register (RFC 7591) and save.
        4. Build the login URL.
        """
        if not self._login:
            return None

        resolved = config or self._resolve_config(user_id, server_identifier)

        if not resolved.get("client_id"):
            resolved = await self._try_auto_register(
                user_id, server_identifier, resolved,
            )

        if not resolved or not resolved.get("client_id"):
            return None

        return await self._login.build_login_url(user_id, server_identifier, resolved)

    async def _try_auto_register(
        self,
        user_id: str,
        server_identifier: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Attempt RFC 7591 Dynamic Client Registration.

        Checks client_configs first — if a client_id already exists
        (e.g. from a concurrent registration), uses it instead of
        registering again.
        """
        existing = self.get_client_config(user_id, server_identifier)
        if existing and existing.client_id:
            return existing.model_dump()

        reg_endpoint = config.get("registration_endpoint")

        if not reg_endpoint and self._detector:
            http_client = getattr(self._detector, '_http_client', None)
            if http_client:
                from .protocols.oauth2.detection import OAuth2DetectionStrategy
                as_meta = await OAuth2DetectionStrategy._fetch_as_metadata(
                    server_identifier, http_client,
                )
                if as_meta:
                    config = {**config, **as_meta}
                    reg_endpoint = config.get("registration_endpoint")

        if not reg_endpoint:
            return config

        callback_url = getattr(self._login, '_callback_url', None) if self._login else None
        redirect_uris = [callback_url] if callback_url else None

        supported_methods = config.get("token_endpoint_auth_methods_supported", [])
        auth_method = supported_methods[0] if supported_methods else "none"

        try:
            result = await self._protocol.register_client(
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

    # ── Binding ───────────────────────────────────────────────────────

    def bind(
        self, user_id: str, server_identifier: str,
    ) -> Optional[AuthCredential]:
        """Create a credential handle for a specific user + server.

        Returns a :class:`BoundCredential` whose ``get_headers()`` always
        returns fresh headers (refreshing transparently if needed).
        Returns ``None`` if no stored credential exists.
        """
        if not user_id or not server_identifier:
            return None
        if not self.get_credential(user_id, server_identifier):
            return None

        config = self._resolve_config(user_id, server_identifier)
        return BoundCredential(
            auth_service=self,
            user_id=user_id,
            server_identifier=server_identifier,
            config=config,
        )

    def bind_lazy(
        self,
        ctx_holder: Any,
        server_identifier: str,
    ) -> Optional[AuthCredential]:
        """Create a credential handle with deferred user_id resolution.

        Like :meth:`bind`, but accepts an ``ExecutionContextHolder``
        instead of a ``user_id`` string.  The holder is read at runtime
        (when ``get_headers()`` is called), not at construction time.

        Use this when building sessions — the holder is filled later
        by ``lifecycle.begin()``.
        """
        if not server_identifier:
            return None

        config = self._resolve_config("", server_identifier)
        return BoundCredential(
            auth_service=self,
            user_id=ctx_holder,
            server_identifier=server_identifier,
            config=config,
        )

    # ── Internals ────────────────────────────────────────────────────

    def _resolve_config(
        self, user_id: str, server_identifier: str,
    ) -> Dict[str, Any]:
        cfg = self.get_client_config(user_id, server_identifier)
        return cfg.model_dump() if cfg else {}

    def _refresh(
        self,
        cred: StoredCredential,
        config: Dict[str, Any],
        *,
        raise_on_error: bool = False,
    ) -> Optional[str]:
        if not cred.refresh_token:
            if raise_on_error:
                raise TokenRefreshError("No refresh token available")
            return None
        try:
            from global_utils.utils.async_bridge import get_async_bridge
            with get_async_bridge() as bridge:
                return bridge.run(self._do_refresh(cred, config))
        except Exception as exc:
            if raise_on_error:
                raise
            logger.info(
                "Refresh failed for server=%s: %s",
                cred.server_identifier, exc,
            )
            return None

    async def _do_refresh(
        self, cred: StoredCredential, config: Dict[str, Any],
    ) -> str:
        try:
            new_tokens: TokenSet = await self._protocol.refresh(
                config, cred.refresh_token,
            )
        except Exception as exc:
            self._store.update_status(
                cred.user_id,
                cred.server_identifier,
                TokenStatus.REFRESH_FAILED.value,
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
        self._store.upsert(updated)
        logger.debug(
            "Token refreshed for user=%s server=%s",
            cred.user_id, cred.server_identifier,
        )
        return updated.access_token
