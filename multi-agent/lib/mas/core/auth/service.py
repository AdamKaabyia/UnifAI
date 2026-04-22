"""
AuthService — thin credential-lifecycle service.

Owns: lookup, header building, validation, recovery.
Does NOT own: login flows, code exchange, DCR — those are scheme-specific
and live in their respective scheme packages.

All I/O methods (get_headers, get_valid_token, attempt_recovery) are async
because they may need to call external token endpoints. 

Also contains :class:`BoundCredential`, the handle that elements
receive at build time so they can call ``get_headers()`` with no args.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from .errors import TokenExpiredError
from .credentials.models import (
    StoredCredential, TokenStatus, RecoveryResult, ClientConfig,
)
from .credentials.ports import TokenStore, ClientConfigStore
from .ports import AuthScheme

if TYPE_CHECKING:
    from .credentials.credential import AuthCredential

logger = logging.getLogger(__name__)


class SchemeRegistry:
    """Maps scheme_type strings to AuthScheme instances."""

    def __init__(self) -> None:
        self._schemes: Dict[str, AuthScheme] = {}

    def register(self, scheme: AuthScheme) -> None:
        self._schemes[scheme.scheme_type] = scheme

    def get(self, scheme_type: str) -> AuthScheme:
        try:
            return self._schemes[scheme_type]
        except KeyError:
            raise ValueError(f"Unknown auth scheme: {scheme_type!r}")


class BoundCredential:
    """Binds AuthService to a specific (user, server) pair.

    Satisfies :class:`AuthCredential` so consumers can call
    ``await get_headers()`` / ``await get_token()`` /
    ``await attempt_recovery()`` without passing user_id and
    server_identifier every time.

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

    async def get_headers(self) -> Dict[str, str]:
        return await self._svc.get_headers(
            self._user_id, self._server_id, self._config,
        )

    async def get_token(self) -> str:
        token = await self._svc.get_valid_token(
            self._user_id, self._server_id, self._config,
        )
        if not token:
            raise TokenExpiredError("No valid token")
        return token

    async def attempt_recovery(self) -> RecoveryResult:
        return await self._svc.attempt_recovery(
            self._user_id, self._server_id, self._config,
        )


class AuthService:

    def __init__(
        self,
        token_store: TokenStore,
        scheme_registry: SchemeRegistry,
        client_config_store: Optional[ClientConfigStore] = None,
    ):
        self._store = token_store
        self._schemes = scheme_registry
        self._configs = client_config_store

    # ── Credential CRUD (sync — pure DB, no external I/O) ────────────

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

    # ── Token access (async — may trigger refresh I/O) ────────────────

    async def get_valid_token(
        self,
        user_id: str,
        server_identifier: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Return a valid access token, attempting recovery if expired."""
        cred = self.get_credential(user_id, server_identifier)
        if cred and cred.is_valid():
            return cred.access_token

        if cred:
            recovery = await self.attempt_recovery(user_id, server_identifier, config)
            if recovery.recovered and recovery.new_token_set:
                return recovery.new_token_set.access_token
        return None

    async def get_headers(
        self,
        user_id: str,
        server_identifier: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        cred = self.get_credential(user_id, server_identifier)
        if not cred:
            raise TokenExpiredError(
                f"No credential for user={user_id} server={server_identifier}"
            )

        if not cred.is_valid():
            recovery = await self.attempt_recovery(user_id, server_identifier, config)
            if recovery.recovered:
                cred = self.get_credential(user_id, server_identifier)
            if not cred or not cred.is_valid():
                raise TokenExpiredError(
                    f"Credential expired and recovery failed for server={server_identifier}"
                )

        scheme = self._schemes.get(cred.scheme_type)
        return scheme.build_headers(cred)

    # ── Validation ────────────────────────────────────────────────────

    async def is_token_valid(
        self,
        user_id: str,
        server_identifier: str,
        url: str,
    ) -> bool:
        """Real connection check — probe *url* with the stored token."""
        cred = self.get_credential(user_id, server_identifier)
        if not cred or not cred.is_valid():
            return False
        scheme = self._schemes.get(cred.scheme_type)
        return await scheme.validate(cred, url)

    # ── Recovery (async — calls external token endpoint) ──────────────

    async def attempt_recovery(
        self,
        user_id: str,
        server_identifier: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> RecoveryResult:
        """Delegate recovery to the appropriate scheme and persist the result."""
        cred = self.get_credential(user_id, server_identifier)
        if not cred:
            return RecoveryResult(
                recovered=False, should_retry=False,
                reason="No credential found",
            )

        scheme = self._schemes.get(cred.scheme_type)
        resolved = config or self._resolve_config(user_id, server_identifier)

        try:
            result = await scheme.attempt_recovery(cred, resolved)
        except Exception as exc:
            logger.info("Recovery failed for server=%s: %s", server_identifier, exc)
            return RecoveryResult(
                recovered=False, should_retry=False,
                reason=f"Recovery error: {exc}",
            )

        if result.recovered and result.new_token_set:
            updated = StoredCredential(
                id=cred.id,
                user_id=cred.user_id,
                server_identifier=cred.server_identifier,
                access_token=result.new_token_set.access_token,
                refresh_token=result.new_token_set.refresh_token or cred.refresh_token,
                token_type=result.new_token_set.token_type,
                expires_at=result.new_token_set.expires_at or cred.expires_at,
                scopes=cred.scopes,
                scheme_type=cred.scheme_type,
                status=TokenStatus.ACTIVE,
            )
            self._store.upsert(updated)
            logger.debug(
                "Credential recovered for user=%s server=%s",
                cred.user_id, cred.server_identifier,
            )

        return result

    # ── Binding ───────────────────────────────────────────────────────

    def bind(
        self, user_id: str, server_identifier: str,
    ) -> Optional[AuthCredential]:
        """Create a credential handle for a specific user + server.

        Returns a :class:`BoundCredential` whose ``get_headers()`` always
        returns fresh headers (recovering transparently if needed).
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

    # ── Internals ─────────────────────────────────────────────────────

    def _resolve_config(
        self, user_id: str, server_identifier: str,
    ) -> Dict[str, Any]:
        cfg = self.get_client_config(user_id, server_identifier)
        return cfg.model_dump() if cfg else {}
