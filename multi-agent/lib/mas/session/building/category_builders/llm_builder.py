from typing import Any, Iterable
from .category_builder import CategoryBuilder, BlueprintSpec
from mas.core.enums import ResourceCategory


class LLMBuilder(CategoryBuilder):
    category = ResourceCategory.LLM

    def _iter_specs(self, blueprint: BlueprintSpec) -> Iterable[Any]:
        return blueprint.llms


