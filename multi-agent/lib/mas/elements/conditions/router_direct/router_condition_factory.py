from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import RouterDirectConditionConfig
from .router import RouterDirectCondition
from .identifiers import Identifier


class RouterDirectConditionFactory(BaseFactory[RouterDirectConditionConfig, RouterDirectCondition]):
    """Factory for RouterDirectCondition."""

    def accepts(self, cfg: RouterDirectConditionConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: RouterDirectConditionConfig, **deps) -> RouterDirectCondition:
        """
        deps delivers at least:
          • step_ctx  – mandatory identity capsule
        """
        try:
            return RouterDirectCondition()
        except Exception as exc:
            raise PluginConfigurationError(
                f"RouterDirectConditionFactory.create failed: {exc}",
                cfg.dict()
            ) from exc