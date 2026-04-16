from typing import Any, Iterable

from .category_builder import CategoryBuilder, BlueprintSpec
from mas.core.enums import ResourceCategory
from mas.core.contracts import SessionRegistry


class ProviderBuilder(CategoryBuilder):
    category = ResourceCategory.PROVIDER
    depends_on = (ResourceCategory.AUTH,)

    def _iter_specs(self, blueprint: BlueprintSpec) -> Iterable[Any]:
        return blueprint.providers

    def _extra_kwargs(self, cfg: Any, session_registry: SessionRegistry) -> dict[str, Any]:
        # Path 1: auth element selected → get credential from session registry
        auth_ref = getattr(cfg, "auth", None)
        if auth_ref is not None:
            auth_instance = session_registry.get_instance(ResourceCategory.AUTH, auth_ref.ref)
            return {"auth_credential": auth_instance}

        # Path 2: server_identifier set (auto-discovery) → build credential directly
        server_id = getattr(cfg, "server_identifier", "")
        if server_id:
            return {"server_identifier": server_id}

        return {}
