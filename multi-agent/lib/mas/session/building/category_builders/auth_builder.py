from typing import Any, Iterable

from .category_builder import CategoryBuilder, BlueprintSpec
from mas.core.enums import ResourceCategory


class AuthBuilder(CategoryBuilder):
    """Builds auth element instances before providers that depend on them."""
    category = ResourceCategory.AUTH

    def _iter_specs(self, blueprint: BlueprintSpec) -> Iterable[Any]:
        return blueprint.auths
