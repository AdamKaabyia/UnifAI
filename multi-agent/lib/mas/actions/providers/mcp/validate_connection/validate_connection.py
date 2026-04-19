"""
MCP validate_connection action.

Tests a real MCP connection via the factory.
On 401: uses AuthService for discovery and login URL.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

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
    transport_type: McpTransportType = Field(default=McpTransportType.STREAMABLE_HTTP)
    additional_headers: Dict[str, Any] = Field(default_factory=dict)


class ValidateConnectionOutput(BaseActionOutput):
    is_reachable: bool = False
    authenticated: bool = False
    auth_required: bool = False
    status: str = ""
    server_identifier: str = ""
    authorization_url: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)
    response_time_ms: float = 0.0


class ValidateConnectionAction(BaseAction):
    uid = "mcp.validate_connection"
    name = "validate_connection"
    description = "Validate MCP server connection and authentication status"
    action_type = ActionType.VALIDATION
    input_schema = ValidateConnectionInput
    output_schema = ValidateConnectionOutput
    version = "4.0.0"
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
            if "cancel scope" in str(e).lower():
                return self._handle_auth_required_sync(input_data)
            return ValidateConnectionOutput(
                success=False, message=f"Connection failed: {e}",
                is_reachable=False,
            )

    async def execute(
        self,
        input_data: ValidateConnectionInput,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidateConnectionOutput:
        start = time.time()
        user_id = input_data.user_id
        server_id = input_data.server_identifier

        auth_cred = None
        if self._auth and user_id and server_id:
            auth_cred = self._auth.bind(user_id, server_id)

        config = McpProviderConfig(
            mcp_url=input_data.mcp_url,
            transport_type=input_data.transport_type,
            additional_headers=input_data.additional_headers,
        )

        try:
            await self._factory.create_async(config, auth_credential=auth_cred)
            elapsed = (time.time() - start) * 1000
            return ValidateConnectionOutput(
                success=True, message=f"Connected ({elapsed:.0f}ms)",
                is_reachable=True, authenticated=bool(auth_cred),
                status="authenticated" if auth_cred else "",
                server_identifier=server_id,
                response_time_ms=elapsed,
            )

        except TimeoutError:
            return ValidateConnectionOutput(
                success=False, message="Connection timeout",
                is_reachable=False,
                response_time_ms=(time.time() - start) * 1000,
            )

        except Exception as e:
            return ValidateConnectionOutput(
                success=False, message=f"Connection failed: {e}",
                is_reachable=False,
                response_time_ms=(time.time() - start) * 1000,
            )

    def _handle_auth_required_sync(
        self, input_data: ValidateConnectionInput,
    ) -> ValidateConnectionOutput:
        """Handle 401: discover auth server, build login URL if possible (sync)."""
        server_id = input_data.server_identifier
        user_id = input_data.user_id
        scopes: List[str] = []

        from global_utils.utils.async_bridge import get_async_bridge

        if not server_id and self._auth:
            try:
                with get_async_bridge() as bridge:
                    detection = bridge.run(
                        self._auth.discover(str(input_data.mcp_url))
                    )
                    if detection:
                        server_id = detection.server_identifier
                        scopes = detection.scopes_supported
            except Exception as exc:
                logger.debug("Auth discovery failed: %s", exc)

        if server_id and user_id and self._auth:
            token = self._auth.get_valid_token(user_id, server_id)
            if token:
                updated_input = input_data.model_copy(
                    update={"server_identifier": server_id}
                )
                try:
                    with get_async_bridge() as bridge:
                        return bridge.run(self.execute(updated_input))
                except Exception as exc:
                    logger.debug("Authenticated retry failed: %s", exc)

            try:
                with get_async_bridge() as bridge:
                    url = bridge.run(
                        self._auth.build_login_url(user_id, server_id)
                    )
                    if url:
                        client_cfg = self._auth.get_client_config(user_id, server_id)
                        return ValidateConnectionOutput(
                            success=True, message="Sign in required",
                            status="requires_consent", is_reachable=True,
                            auth_required=True, server_identifier=server_id,
                            authorization_url=url,
                            scopes=client_cfg.scopes if client_cfg else scopes,
                        )
            except Exception as exc:
                logger.debug("Login URL build failed: %s", exc)

        return ValidateConnectionOutput(
            success=True, message="Authentication required",
            status="auth_required", is_reachable=True, auth_required=True,
            server_identifier=server_id, scopes=scopes,
        )


