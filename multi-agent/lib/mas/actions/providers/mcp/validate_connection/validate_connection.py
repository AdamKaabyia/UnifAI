"""
MCP validate_connection action.

Connectivity probe. Uses credential_token from the form if provided,
otherwise falls back to stored credential via bind(server_identifier).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from pydantic import HttpUrl, Field

from mas.actions.common.base_action import BaseAction
from mas.actions.common.action_models import BaseActionInput, BaseActionOutput, ActionType
from mas.core.auth.service import AuthService
from mas.core.enums import ResourceCategory
from mas.elements.providers.mcp_server_client.mcp_provider_factory import McpProviderFactory
from mas.elements.providers.mcp_server_client.config import McpProviderConfig
from mas.elements.providers.mcp_server_client.identifiers import Identifier
from mas.elements.providers.mcp_server_client.transport.enums import McpTransportType

logger = logging.getLogger(__name__)


class ValidateConnectionInput(BaseActionInput):
    mcp_url: HttpUrl
    user_id: str = Field(default="")
    server_identifier: str = Field(default="")
    credential_token: Optional[str] = Field(default=None)
    transport_type: McpTransportType = Field(default=McpTransportType.STREAMABLE_HTTP)
    additional_headers: Dict[str, Any] = Field(default_factory=dict)


class ValidateConnectionOutput(BaseActionOutput):
    is_reachable: bool = False
    authenticated: bool = False
    status: str = ""
    server_identifier: str = ""
    response_time_ms: float = 0.0


class ValidateConnectionAction(BaseAction):
    uid = "mcp.validate_connection"
    name = "validate_connection"
    description = "Validate MCP server connectivity"
    action_type = ActionType.VALIDATION
    input_schema = ValidateConnectionInput
    output_schema = ValidateConnectionOutput
    version = "10.0.0"
    tags = {"mcp", "validation", "connectivity"}
    elements = {(ResourceCategory.PROVIDER.value, Identifier.TYPE)}

    def __init__(
        self,
        factory: Optional[McpProviderFactory] = None,
        auth_service: Optional[AuthService] = None,
    ):
        super().__init__()
        self._factory = factory or McpProviderFactory()
        self._auth = auth_service

    def execute_sync(self, input_data, context=None):
        try:
            return super().execute_sync(input_data, context)
        except RuntimeError as e:
            return ValidateConnectionOutput(
                success=False, message=f"Connection failed: {e}",
                is_reachable=False,
            )

    async def execute(self, input_data, context=None):
        start = time.time()
        mcp_url = str(input_data.mcp_url)
        user_id = input_data.user_id
        server_id = input_data.server_identifier

        auth_cred = self._auth.bind(user_id, server_id) if (self._auth and user_id and server_id and not input_data.credential_token) else None

        config = McpProviderConfig(
            mcp_url=input_data.mcp_url,
            bearer_token=input_data.credential_token or None,
            transport_type=input_data.transport_type,
            additional_headers=input_data.additional_headers,
        )

        try:
            import anyio
            with anyio.fail_after(10.0):
                await self._factory.create_async(config, auth_credential=auth_cred)
            elapsed = (time.time() - start) * 1000
            is_authed = bool(input_data.credential_token) or bool(auth_cred)
            return ValidateConnectionOutput(
                success=True,
                message=f"Connected ({elapsed:.0f}ms)",
                is_reachable=True,
                authenticated=is_authed,
                status="authenticated" if is_authed else "",
                server_identifier=server_id or mcp_url,
                response_time_ms=elapsed,
            )
        except TimeoutError:
            return ValidateConnectionOutput(
                success=False, message="Connection timeout",
                is_reachable=False,
                response_time_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            if "cancel scope" in str(e).lower():
                return ValidateConnectionOutput(
                    success=True,
                    message="Server is reachable but requires authentication",
                    is_reachable=True,
                    authenticated=False,
                    status="auth_required",
                    server_identifier=mcp_url,
                    response_time_ms=(time.time() - start) * 1000,
                )
            return ValidateConnectionOutput(
                success=False, message=f"Connection failed: {e}",
                is_reachable=False,
                response_time_ms=(time.time() - start) * 1000,
            )
