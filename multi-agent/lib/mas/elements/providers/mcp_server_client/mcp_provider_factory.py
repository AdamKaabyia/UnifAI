from typing import Any, Dict, Optional
from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import McpProviderConfig
from .mcp_provider import McpProvider
from .identifiers import Identifier


class McpProviderFactory(BaseFactory[McpProviderConfig, McpProvider]):
    """
    Factory for creating MCP Provider instances from McpProviderConfig.
    """

    def accepts(self, cfg: McpProviderConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def _build_headers(
        self,
        bearer_token: Optional[str],
        additional_headers: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Build HTTP headers from bearer token and any additional headers.

        Args:
            bearer_token: Optional bearer token for authentication
            additional_headers: Optional extra headers to include

        Returns:
            Merged headers dict, or None if no headers are needed
        """
        headers: Dict[str, Any] = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        if additional_headers:
            headers.update(additional_headers)
        return headers if headers else None

    def create(self, cfg: McpProviderConfig, **kwargs: Any) -> McpProvider:
        """
        Instantiate an McpProvider using validated config values.

        :param cfg: Fully‐validated McpProviderConfig
        :raises PluginConfigurationError: if instantiation fails
        """
        try:
            headers = self._build_headers(cfg.bearer_token, cfg.additional_headers)
            
            # Use the clean sync factory method which handles async internally
            return McpProvider.create_sync(
                mcp_url=cfg.mcp_url,
                tool_names=cfg.tool_names,
                headers=headers,
                transport_type=cfg.transport_type,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"McpProvider.create() failed: {e}",
                cfg.dict()
            ) from e

    async def create_async(self, cfg: McpProviderConfig, **kwargs: Any) -> McpProvider:
        """
        Async version of create() for better performance when called from async context.

        :param cfg: Fully‐validated McpProviderConfig
        :raises PluginConfigurationError: if instantiation fails
        """
        try:
            headers = self._build_headers(cfg.bearer_token, cfg.additional_headers)
            
            # Use the async factory method directly for better performance
            return await McpProvider.create_async(
                mcp_url=cfg.mcp_url,
                tool_names=cfg.tool_names,
                headers=headers,
                transport_type=cfg.transport_type,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"McpProvider.create_async() failed: {e}",
                cfg.dict()
            ) from e