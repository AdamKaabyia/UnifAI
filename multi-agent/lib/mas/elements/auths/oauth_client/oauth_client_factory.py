"""
Factory that builds auth element instances from validated config.

Auth elements are UI widgets for login — they don't produce runtime
credentials for providers.  Providers get tokens directly from AuthService.
"""

from __future__ import annotations

import logging
from typing import Any

from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError

from .config import OAuthClientConfig
from .identifiers import Identifier

logger = logging.getLogger(__name__)

_ACCEPTED_TYPES = frozenset({
    "oauth_client", "google_oauth", "github_oauth", "jira_oauth",
})


class _NullAuthHandle:
    """Placeholder returned when no AuthService is available."""

    async def get_headers(self):
        return {}

    async def get_token(self):
        from mas.core.auth.errors import TokenExpiredError
        raise TokenExpiredError("No auth service configured")

    async def attempt_recovery(self):
        from mas.core.auth.credentials.models import RecoveryResult
        return RecoveryResult(
            recovered=False, should_retry=False,
            reason="No auth service configured",
        )


class OAuthClientFactory(BaseFactory[OAuthClientConfig, Any]):

    def accepts(self, cfg: OAuthClientConfig, element_type: str) -> bool:
        return element_type in _ACCEPTED_TYPES

    def create(self, cfg: OAuthClientConfig, **kwargs: Any) -> Any:
        try:
            return _NullAuthHandle()
        except Exception as e:
            raise PluginConfigurationError(
                f"OAuthClientFactory.create() failed: {e}",
                cfg.model_dump(),
            ) from e
