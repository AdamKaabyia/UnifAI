"""
Factory that builds :class:`OAuthClientInstance` from validated config.
"""

from __future__ import annotations

import logging
from typing import Any

from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError

from .config import OAuthClientConfig
from .identifiers import Identifier
from .oauth_client_instance import OAuthClientInstance

logger = logging.getLogger(__name__)

_ACCEPTED_TYPES = frozenset({
    "oauth_client", "google_oauth", "github_oauth", "jira_oauth",
})


class OAuthClientFactory(BaseFactory[OAuthClientConfig, OAuthClientInstance]):

    def accepts(self, cfg: OAuthClientConfig, element_type: str) -> bool:
        return element_type in _ACCEPTED_TYPES

    def create(self, cfg: OAuthClientConfig, **kwargs: Any) -> OAuthClientInstance:
        try:
            deps = kwargs.get("deps")
            auth_service = getattr(deps, "auth_service", None) if deps else None
            exec_ctx = getattr(deps, "execution_ctx", None) if deps else None

            if auth_service and exec_ctx and cfg.server_identifier:
                cred = auth_service.bind_lazy(exec_ctx, cfg.server_identifier)
                if cred:
                    return cred

            return OAuthClientInstance()

        except Exception as e:
            raise PluginConfigurationError(
                f"OAuthClientFactory.create() failed: {e}",
                cfg.model_dump(),
            ) from e
