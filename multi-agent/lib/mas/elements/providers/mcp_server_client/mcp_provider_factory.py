from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING
from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import McpProviderConfig
from .mcp_provider import McpProvider
from .identifiers import Identifier

if TYPE_CHECKING:
    from mas.core.auth.credentials.credential import AuthCredential

logger = logging.getLogger(__name__)


class McpProviderFactory(BaseFactory[McpProviderConfig, McpProvider]):

    def accepts(self, cfg: McpProviderConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def _resolve_auth(self, cfg: McpProviderConfig, kwargs: Dict[str, Any]) -> Optional[AuthCredential]:
        """Resolve auth from either auth element (Path 1) or server_identifier (Path 2)."""
        # Path 1: auth element credential passed by ProviderBuilder
        auth = kwargs.get("auth_credential")
        if auth:
            return auth

        # Path 2: server_identifier passed by ProviderBuilder → build credential from token store
        server_id = kwargs.get("server_identifier", "")
        if not server_id:
            return None

        deps = kwargs.get("deps")
        auth_infra = getattr(deps, "auth_infra", None) if deps else None
        if not auth_infra:
            return None

        exec_ctx = getattr(deps, "execution_ctx", None)
        user_id = getattr(exec_ctx, "user_id", None) if exec_ctx else None
        if not user_id:
            return None

        runtime_config = {}
        if auth_infra.client_config_store:
            client_cfg = auth_infra.client_config_store.find_by_server(user_id, server_id)
            if client_cfg:
                runtime_config = client_cfg.model_dump()

        from mas.core.auth.credentials.store import CredentialService
        from mas.core.auth.credentials.lifecycle import TokenLifecycleService
        cred_service = CredentialService(auth_infra.token_store)
        lifecycle = TokenLifecycleService(cred_service, auth_infra.protocol)

        from mas.elements.auths.oauth_client.oauth_client_instance import OAuthClientInstance
        return OAuthClientInstance(
            lifecycle=lifecycle,
            user_id=user_id,
            server_identifier=server_id,
            config=runtime_config,
        )

    def _resolve_headers(
        self,
        cfg: McpProviderConfig,
        auth: Optional[AuthCredential] = None,
    ) -> Optional[Dict[str, Any]]:
        headers: Dict[str, Any] = {}
        if cfg.additional_headers:
            headers.update(cfg.additional_headers)
        if auth:
            try:
                headers = {**auth.get_headers(), **headers}
            except Exception as exc:
                logger.warning("Auth token unavailable at build time: %s", exc)
        return headers if headers else None

    def create(self, cfg: McpProviderConfig, **kwargs: Any) -> McpProvider:
        try:
            auth = self._resolve_auth(cfg, kwargs)
            headers = self._resolve_headers(cfg, auth)

            return McpProvider.create_sync(
                mcp_url=cfg.mcp_url,
                tool_names=cfg.tool_names,
                headers=headers,
                transport_type=cfg.transport_type,
                auth=auth,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"McpProvider.create() failed: {e}", cfg.dict(),
            ) from e

    async def create_async(self, cfg: McpProviderConfig, **kwargs: Any) -> McpProvider:
        try:
            auth = self._resolve_auth(cfg, kwargs)
            headers = self._resolve_headers(cfg, auth)

            return await McpProvider.create_async(
                mcp_url=cfg.mcp_url,
                tool_names=cfg.tool_names,
                headers=headers,
                transport_type=cfg.transport_type,
                auth=auth,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"McpProvider.create_async() failed: {e}", cfg.dict(),
            ) from e
