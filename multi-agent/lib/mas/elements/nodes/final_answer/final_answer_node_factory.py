from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import FinalAnswerNodeConfig
from .final_answer import FinalAnswerNode
from .identifiers import Identifier


class FinalAnswerNodeFactory(BaseFactory[FinalAnswerNodeConfig, FinalAnswerNode]):
    """Builds a FinalAnswerNode (no LLM / retriever / tools needed)."""

    def accepts(self, cfg: FinalAnswerNodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: FinalAnswerNodeConfig, **deps) -> FinalAnswerNode:
        try:
            return FinalAnswerNode()
        except Exception as exc:
            raise PluginConfigurationError(
                f"FinalAnswerNodeFactory.create failed: {exc}",
                cfg.dict()
            ) from exc
