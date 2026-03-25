from .category_builder import CategoryBuilder, BlueprintSpec
from mas.core.enums import ResourceCategory
from typing import Iterable, Any


class RetrieverBuilder(CategoryBuilder):
    category = ResourceCategory.RETRIEVER

    def _iter_specs(self, blueprint: BlueprintSpec) -> Iterable[Any]:
        return blueprint.retrievers
