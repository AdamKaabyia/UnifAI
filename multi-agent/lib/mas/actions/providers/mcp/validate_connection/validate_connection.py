"""
MCP validate_connection action.

Tests a real MCP connection via the factory.
On 401: uses AuthService.discover() + AuthService.initiate() for login.
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
    challenge: Optional[Dict[str, Any]] = None


class ValidateConnectionAction(BaseAction):
    uid = "mcp.validate_connection"
    name = "validate_connection"
    description = "Validate MCP server connection and authentication status"
    action_type = ActionType.VALIDATION
    input_schema = ValidateConnectionInput
    output_schema = ValidateConnectionOutput
    version = "6.0.0"
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
        """Handle 401: discover auth via AuthService, initiate if possible (sync)."""
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
            try:
                with get_async_bridge() as bridge:
                    token = bridge.run(self._auth.get_valid_token(user_id, server_id))
            except Exception as exc:
                logger.warning("Token lookup/refresh failed: %s", exc)
                token = None
            logger.info(
                "Auth retry: user=%s server=%s token_found=%s",
                user_id, server_id, bool(token),
            )
            if token:
                auth_cred = self._auth.bind(user_id, server_id)
                config = McpProviderConfig(
                    mcp_url=input_data.mcp_url,
                    transport_type=input_data.transport_type,
                    additional_headers=input_data.additional_headers,
                )
                try:
                    start = time.time()
                    with get_async_bridge() as bridge:
                        bridge.run(
                            self._factory.create_async(config, auth_credential=auth_cred)
                        )
                    elapsed = (time.time() - start) * 1000
                    return ValidateConnectionOutput(
                        success=True, message=f"Connected ({elapsed:.0f}ms)",
                        is_reachable=True, authenticated=True,
                        status="authenticated",
                        server_identifier=server_id,
                        response_time_ms=elapsed,
                    )
                except Exception as exc:
                    logger.warning(
                        "Authenticated retry failed for server=%s: %s",
                        server_id, exc,
                    )
                    return ValidateConnectionOutput(
                        success=False,
                        message="Authenticated, but the server still rejected the request. "
                                "Check that all required headers are configured in 'Additional Headers'.",
                        status="authenticated_but_rejected",
                        is_reachable=True,
                        authenticated=True,
                        auth_required=False,
                        server_identifier=server_id,
                    )

            try:
                client_cfg = self._auth.get_client_config(user_id, server_id)
                login_config = client_cfg.model_dump() if client_cfg else {}
                with get_async_bridge() as bridge:
                    challenge = bridge.run(
                        self._auth.initiate(
                            user_id, server_id,
                            scheme_type="oauth2",
                            config=login_config,
                        )
                    )
                    resp = challenge.to_response()
                    return ValidateConnectionOutput(
                        success=True, message="Sign in required",
                        status="requires_consent", is_reachable=True,
                        auth_required=True, server_identifier=server_id,
                        authorization_url=resp.get("authorization_url"),
                        scopes=resp.get("scopes", scopes),
                        challenge=resp,
                    )
            except Exception as exc:
                logger.error("Auth initiation failed: %s", exc, exc_info=True)

        return ValidateConnectionOutput(
            success=True, message="Authentication required",
            status="auth_required", is_reachable=True, auth_required=True,
            server_identifier=server_id, scopes=scopes,
        )
