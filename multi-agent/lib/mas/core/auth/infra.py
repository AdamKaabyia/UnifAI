"""
AuthInfra -- bundle of auth ports for injection via ElementDeps.

Provides :meth:`resolve_credential` as the single entry point for
any consumer that needs an authenticated credential.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from .ports import AuthProtocol
from .credentials.ports import TokenStore
from .credentials.client_config import ClientConfigStore
from .credentials.store import CredentialService
from .credentials.lifecycle import TokenLifecycleService

if TYPE_CHECKING:
    from .credentials.credential import AuthCredential

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthInfra:
    """Immutable bundle passed through :class:`ElementDeps`."""
    token_store: TokenStore
    protocol: AuthProtocol
    client_config_store: Optional[ClientConfigStore] = None

    def resolve_credential(
        self, user_id: str, server_identifier: str,
    ) -> Optional[AuthCredential]:
        """Resolve a live, auto-refreshing credential for the given user + server.

        Returns an :class:`AuthCredential` whose ``get_headers()`` always
        returns fresh headers (refreshing transparently if needed).
        Returns ``None`` if no stored credential exists.
        """
        if not user_id or not server_identifier:
            return None

        cred_service = CredentialService(self.token_store)
        if not cred_service.get_credential(user_id, server_identifier):
            return None

        lifecycle = TokenLifecycleService(cred_service, self.protocol)

        config: dict = {}
        if self.client_config_store:
            client_cfg = self.client_config_store.find_by_server(
                user_id, server_identifier,
            )
            if client_cfg:
                config = client_cfg.model_dump()

        from mas.elements.auths.oauth_client.oauth_client_instance import OAuthClientInstance
        return OAuthClientInstance(
            lifecycle=lifecycle,
            user_id=user_id,
            server_identifier=server_identifier,
            config=config,
        )
