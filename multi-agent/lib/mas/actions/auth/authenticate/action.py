"""
auth.authenticate — scheme-agnostic credential status check and onboarding.

Thin pass-through: asks the auth layer for status, returns the result.
Never interprets or hardcodes scheme-specific logic.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from pydantic import Field

from mas.actions.common.base_action import BaseAction
from mas.actions.common.action_models import (
    BaseActionInput,
    BaseActionOutput,
    ActionType,
)
from mas.core.auth.service import AuthService
from mas.core.enums import ResourceCategory, AuthStatus, AuthErrorCode

logger = logging.getLogger(__name__)


class AuthenticateInput(BaseActionInput):
    user_id: str = Field(default="", description="User performing the auth check")
    server_identifier: str = Field(default="", description="Auth server issuer URL")
    scheme_type: str = Field(default="", description="Auth scheme (oauth2, api_key, …)")


class AuthenticateOutput(BaseActionOutput):
    status: AuthStatus = AuthStatus.ERROR
    authenticated: bool = False
    scheme_type: str = ""
    challenge: Optional[Dict[str, Any]] = None
    error_code: Optional[AuthErrorCode] = None


class AuthenticateAction(BaseAction):
    uid = "auth.authenticate"
    name = "authenticate"
    description = "Check credential status and initiate onboarding if needed"
    action_type = ActionType.VALIDATION
    input_schema = AuthenticateInput
    output_schema = AuthenticateOutput
    version = "4.0.0"
    tags = {"auth", "validation"}
    elements = {
        (ResourceCategory.PROVIDER.value, "mcp_server_client"),
    }

    def __init__(self, auth_service: Optional[AuthService] = None):
        super().__init__()
        self._auth = auth_service

    def execute_sync(self, input_data, context=None):
        try:
            return super().execute_sync(input_data, context)
        except RuntimeError as exc:
            return AuthenticateOutput(
                success=False,
                message=str(exc),
                status=AuthStatus.ERROR,
                error_code=AuthErrorCode.UNKNOWN,
            )

    async def execute(
        self,
        input_data: AuthenticateInput,
        context: Optional[Dict[str, Any]] = None,
    ) -> AuthenticateOutput:
        user_id = input_data.user_id
        server_id = input_data.server_identifier
        scheme = input_data.scheme_type

        if not user_id:
            return AuthenticateOutput(
                success=False,
                message="User ID is required",
                status=AuthStatus.ERROR,
                error_code=AuthErrorCode.MISSING_USER_ID,
            )

        if not server_id:
            return AuthenticateOutput(
                success=False,
                message="Server identifier is required",
                status=AuthStatus.NOT_CONFIGURED,
                error_code=AuthErrorCode.MISSING_SERVER_ID,
            )

        if not self._auth:
            return AuthenticateOutput(
                success=False,
                message="Auth service is not available",
                status=AuthStatus.ERROR,
                error_code=AuthErrorCode.AUTH_SERVICE_UNAVAILABLE,
            )

        token = await self._auth.get_valid_token(user_id, server_id, scheme_type=scheme)
        if token:
            cred = self._auth.get_credential(user_id, server_id, scheme)
            return AuthenticateOutput(
                success=True,
                message="Authenticated",
                status=AuthStatus.AUTHENTICATED,
                authenticated=True,
                scheme_type=cred.scheme_type if cred else scheme,
            )

        if not scheme:
            return AuthenticateOutput(
                success=False,
                message="No scheme type specified and no existing credential to infer from",
                status=AuthStatus.NOT_CONFIGURED,
                error_code=AuthErrorCode.MISSING_SCHEME_TYPE,
            )

        config = self._auth.get_client_config("", server_id)
        login_config = config.model_dump() if config else {}

        try:
            challenge = await self._auth.initiate(
                user_id, server_id,
                scheme_type=scheme,
                config=login_config,
            )
            return AuthenticateOutput(
                success=True,
                message="Credential required",
                status=AuthStatus.CHALLENGE,
                scheme_type=scheme,
                challenge=challenge.to_response(),
            )
        except Exception as exc:
            logger.warning("Auth initiation failed for server=%s: %s", server_id, exc)
            return AuthenticateOutput(
                success=False,
                message=str(exc),
                status=AuthStatus.NOT_CONFIGURED,
                error_code=AuthErrorCode.INITIATION_FAILED,
                scheme_type=scheme,
            )
