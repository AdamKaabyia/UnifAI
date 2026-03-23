from .category_builder import CategoryBuilder, BlueprintSpec
from mas.core.enums import ResourceCategory
from typing import Iterable, Any


class ConditionBuilder(CategoryBuilder):
    category = ResourceCategory.CONDITION

    def _iter_specs(self, blueprint: BlueprintSpec) -> Iterable[Any]:
        return blueprint.conditions
