from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import RouterBooleanConditionConfig
from .router import RouterBooleanCondition
from .identifiers import Identifier


class RouterBooleanConditionFactory(BaseFactory[RouterBooleanConditionConfig, RouterBooleanCondition]):
    """Factory for RouterBooleanCondition."""

    def accepts(self, cfg: RouterBooleanConditionConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: RouterBooleanConditionConfig, **deps) -> RouterBooleanCondition:
        """
        deps delivers at least:
          • step_ctx  – mandatory identity capsule
        """
        try:
            return RouterBooleanCondition(
                boolean_value=cfg.boolean_value
            )
        except Exception as exc:
            raise PluginConfigurationError(
                f"RouterBooleanConditionFactory.create failed: {exc}",
                cfg.dict()
            ) from exc