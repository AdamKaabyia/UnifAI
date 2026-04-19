from typing import Any, Iterable, Optional

from .category_builder import CategoryBuilder, BlueprintSpec
from mas.core.enums import ResourceCategory
from mas.core.contracts import SessionRegistry
from mas.core.element_deps import ElementDeps


class ProviderBuilder(CategoryBuilder):
    category = ResourceCategory.PROVIDER
    depends_on = (ResourceCategory.AUTH,)

    def _iter_specs(self, blueprint: BlueprintSpec) -> Iterable[Any]:
        return blueprint.providers

    def _extra_kwargs(
        self, cfg: Any, session_registry: SessionRegistry, deps: Optional[ElementDeps] = None,
    ) -> dict[str, Any]:
        # Path 1: explicit auth element ref
        auth_ref = getattr(cfg, "auth", None)
        if auth_ref is not None:
            auth_instance = session_registry.get_instance(ResourceCategory.AUTH, auth_ref.ref)
            return {"auth_credential": auth_instance}

        # Path 2: auto-resolve by server_identifier (deferred user_id)
        server_id = getattr(cfg, "server_identifier", "")
        if server_id and deps and deps.auth_service:
            ctx_holder = getattr(deps, "execution_ctx", None)
            if ctx_holder:
                cred = deps.auth_service.bind_lazy(ctx_holder, server_id)
                if cred:
                    return {"auth_credential": cred}

        return {}
