from typing import Any
from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import McpProxyToolConfig
from .mcp_proxy_tool import McpProxyTool
from .identifiers import Identifier
from mas.elements.providers.mcp_server_client.mcp_server_client import McpServerClient


class McpProxyToolFactory(BaseFactory[McpProxyToolConfig, McpProxyTool]):
    """
    Factory for creating Division clients from an DivisionToolConfig.
    """

    def accepts(self, cfg: McpProxyToolConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: McpProxyToolConfig, **kwargs: Any) -> McpProxyTool:
        try:
            provider: McpServerClient = kwargs.get("provider")
            client = McpProxyTool(mcp_tool_name=cfg.tool_name, mcp_client=provider)
            return client
        except Exception as e:
            raise PluginConfigurationError(
                f"McpProxyTool.create() failed: {e}",
                cfg.dict()
            ) from e
