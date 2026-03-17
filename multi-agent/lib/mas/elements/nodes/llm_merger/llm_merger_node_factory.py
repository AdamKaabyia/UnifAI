from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import MergerLLMNodeConfig
from .llm_merger import LLMMergerNode
from .identifiers import Identifier


class LLMMergerNodeFactory(BaseFactory[MergerLLMNodeConfig, LLMMergerNode]):
    """Factory for LLMMergerNode."""

    def accepts(self, cfg: MergerLLMNodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: MergerLLMNodeConfig, **deps) -> LLMMergerNode:
        try:
            return LLMMergerNode(
                llm=deps.pop("llm"),
                system_message=cfg.system_message,
                retries=cfg.retries,
            )
        except Exception as exc:
            raise PluginConfigurationError(
                f"LLMMergerNodeFactory.create failed: {exc}",
                cfg.dict()
            ) from exc
