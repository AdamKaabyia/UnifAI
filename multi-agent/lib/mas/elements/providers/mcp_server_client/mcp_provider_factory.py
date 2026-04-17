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
            auth = kwargs.get("auth_credential")
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
            auth = kwargs.get("auth_credential")
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
