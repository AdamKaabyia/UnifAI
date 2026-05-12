from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import DeepAgentNodeConfig
from .deep_agent_node import DeepAgentNode
from .identifiers import Identifier


class DeepAgentNodeFactory(BaseFactory[DeepAgentNodeConfig, DeepAgentNode]):
    """Factory for creating ``DeepAgentNode`` instances from configuration."""

    def accepts(self, cfg: DeepAgentNodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: DeepAgentNodeConfig, **deps) -> DeepAgentNode:
        try:
            return DeepAgentNode(
                llm=deps.pop("llm"),
                retriever=deps.pop("retriever"),
                tools=deps.pop("tools"),
                mcp_providers=deps.pop("providers"),
                system_message=cfg.system_message,
                retries=cfg.retries,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"DeepAgentNodeFactory.create failed: {e}",
                cfg.dict(),
            ) from e
