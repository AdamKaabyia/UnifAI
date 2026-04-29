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
from mas.elements.providers.mcp_server_client.identifiers import Identifier as McpIdentifier

logger = logging.getLogger(__name__)


class AuthenticateInput(BaseActionInput):
    server_identifier: str = Field(default="", description="Auth server issuer URL")
    user_id: str = Field(default="")
    scheme_type: str = Field(default="oauth2", description="Auth scheme to use")


class AuthenticateOutput(BaseActionOutput):
    status: str = "unknown"
    authenticated: bool = False
    authorization_url: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)
    challenge: Optional[Dict[str, Any]] = None


class AuthenticateAction(BaseAction):
    uid = "auth.authenticate"
    name = "authenticate"
    description = "Check authentication status and initiate login if needed"
    action_type = ActionType.VALIDATION
    input_schema = AuthenticateInput
    output_schema = AuthenticateOutput
    version = "3.0.0"
    tags = {"auth", "validation"}
    elements = {
        (ResourceCategory.AUTH.value, "oauth_client"),
        (ResourceCategory.AUTH.value, "google_oauth"),
        (ResourceCategory.AUTH.value, "github_oauth"),
        (ResourceCategory.AUTH.value, "jira_oauth"),
        (ResourceCategory.PROVIDER.value, McpIdentifier.TYPE),
    }

    def __init__(
        self,
        auth_service: Optional[AuthService] = None,
    ):
        super().__init__()
        self._auth = auth_service

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

        if not self._auth:
            return AuthenticateOutput(
                success=False, message="Auth service not configured", status="error",
            )

        token = await self._auth.get_valid_token(user_id, server_id)
        if token:
            return AuthenticateOutput(
                success=True, message="Authenticated",
                status="authenticated", authenticated=True,
            )

        config = self._auth.get_client_config(user_id, server_id)
        login_config = config.model_dump() if config else {}

        try:
            challenge = await self._auth.initiate(
                user_id, server_id,
                scheme_type=input_data.scheme_type,
                config=login_config,
            )
            resp = challenge.to_response()
            return AuthenticateOutput(
                success=True,
                message="Sign in required",
                status="requires_consent",
                authorization_url=resp.get("authorization_url"),
                scopes=resp.get("scopes", []),
                challenge=resp,
            )
        except Exception as exc:
            logger.warning("Failed to initiate auth: %s", exc)
            return AuthenticateOutput(
                success=False,
                message=f"Unable to initiate authentication: {exc}",
                status="not_configured",
            )
