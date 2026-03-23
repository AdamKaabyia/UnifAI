from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import MockAgentNodeConfig
from .mock_agent import MockAgentNode
from .identifiers import Identifier


class MockAgentNodeFactory(BaseFactory[MockAgentNodeConfig, MockAgentNode]):
    """Factory for MockAgentNode (needs no LLM / retriever / tools)."""

    def accepts(self, cfg: MockAgentNodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: MockAgentNodeConfig, **deps) -> MockAgentNode:
        """
        deps delivers at least:
          • step_ctx  – mandatory identity capsule
          • llm / retriever / tools – ignored by this node
        """
        try:
            return MockAgentNode(
                echo_message=getattr(cfg, "echo_message", None)
            )
        except Exception as exc:
            raise PluginConfigurationError(
                f"MockAgentNodeFactory.create failed: {exc}",
                cfg.dict()
            ) from exc
