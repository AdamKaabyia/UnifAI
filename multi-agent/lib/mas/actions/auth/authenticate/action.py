"""
auth.authenticate — check auth status and initiate login if needed.

Called by the UI via ActionHint on auth element forms.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import Field

from mas.actions.common.base_action import BaseAction
from mas.actions.common.action_models import (
    BaseActionInput,
    BaseActionOutput,
    ActionType,
)
from mas.core.auth.service import AuthService
from mas.core.enums import ResourceCategory

logger = logging.getLogger(__name__)


class AuthenticateInput(BaseActionInput):
    server_identifier: str = Field(default="", description="Auth server issuer URL")
    user_id: str = Field(default="")


class AuthenticateOutput(BaseActionOutput):
    status: str = "unknown"
    authenticated: bool = False
    authorization_url: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)


class AuthenticateAction(BaseAction):
    uid = "auth.authenticate"
    name = "authenticate"
    description = "Check authentication status and initiate login if needed"
    action_type = ActionType.VALIDATION
    input_schema = AuthenticateInput
    output_schema = AuthenticateOutput
    version = "2.0.0"
    tags = {"auth", "validation"}
    elements = {
        (ResourceCategory.AUTH.value, "oauth_client"),
        (ResourceCategory.AUTH.value, "google_oauth"),
        (ResourceCategory.AUTH.value, "github_oauth"),
        (ResourceCategory.AUTH.value, "jira_oauth"),
    }

    def __init__(
        self,
        auth_service: Optional[AuthService] = None,
        oauth2_login_service: Optional[Any] = None,
    ):
        super().__init__()
        self._auth = auth_service
        self._login = oauth2_login_service

    def execute_sync(self, input_data, context=None):
        try:
            return super().execute_sync(input_data, context)
        except RuntimeError as e:
            return AuthenticateOutput(success=False, message=str(e), status="error")

    async def execute(
        self,
        input_data: AuthenticateInput,
        context: Optional[Dict[str, Any]] = None,
    ) -> AuthenticateOutput:
        user_id = input_data.user_id
        server_id = input_data.server_identifier

        if not user_id:
            return AuthenticateOutput(
                success=False, message="Missing user_id", status="error",
            )
        if not server_id:
            return AuthenticateOutput(
                success=False, message="Missing server_identifier", status="not_configured",
            )

        if self._auth:
            token = await self._auth.get_valid_token(user_id, server_id)
            if token:
                return AuthenticateOutput(
                    success=True, message="Authenticated",
                    status="authenticated", authenticated=True,
                )

        config = self._auth.get_client_config(user_id, server_id) if self._auth else None
        if not config:
            return AuthenticateOutput(
                success=False,
                message="No client credentials configured for this server",
                status="not_configured",
            )

        if self._login:
            url = await self._login.build_login_url(
                user_id, server_id, config.model_dump(),
            )
            if url:
                return AuthenticateOutput(
                    success=True, message="Sign in required",
                    status="requires_consent",
                    authorization_url=url, scopes=config.scopes,
                )

        return AuthenticateOutput(
            success=False, message="Unable to initiate authentication",
            status="not_configured",
        )
