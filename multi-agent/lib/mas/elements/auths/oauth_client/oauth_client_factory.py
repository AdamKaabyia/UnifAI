"""
Factory that builds :class:`OAuthClientInstance` from validated config.
"""

from __future__ import annotations

import logging
from typing import Any

from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from mas.core.auth.credentials.store import CredentialService
from mas.core.auth.credentials.lifecycle import TokenLifecycleService

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
            auth_infra = getattr(deps, "auth_infra", None) if deps else None
            config_dict = cfg.model_dump(exclude={"auth_status", "type"})

            if not auth_infra or not cfg.server_identifier:
                return OAuthClientInstance(
                    lifecycle=None, user_id="", server_identifier="",
                    config=config_dict,
                )

            exec_ctx = getattr(deps, "execution_ctx", None)
            user_id = getattr(exec_ctx, "user_id", None) if exec_ctx else None
            if not user_id:
                return OAuthClientInstance(
                    lifecycle=None, user_id="", server_identifier="",
                    config=config_dict,
                )

            runtime_config = config_dict
            if auth_infra.client_config_store:
                client_cfg = auth_infra.client_config_store.find_by_server(
                    user_id, cfg.server_identifier,
                )
                if client_cfg:
                    runtime_config = {**config_dict, **client_cfg.model_dump()}

            cred_service = CredentialService(auth_infra.token_store)
            lifecycle = TokenLifecycleService(cred_service, auth_infra.protocol)

            return OAuthClientInstance(
                lifecycle=lifecycle,
                user_id=user_id,
                server_identifier=cfg.server_identifier,
                config=runtime_config,
            )

        except Exception as e:
            raise PluginConfigurationError(
                f"OAuthClientFactory.create() failed: {e}",
                cfg.model_dump(),
            ) from e
