"""
MCP validate_connection action.

Probes an MCP server. On 401: discovers auth server, checks token,
builds login URL if needed.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx
from pydantic import HttpUrl, Field

from mas.actions.common.base_action import BaseAction
from mas.actions.common.action_models import (
    BaseActionInput,
    BaseActionOutput,
    ActionType,
)
from mas.core.auth.credentials.lifecycle import TokenLifecycleService
from mas.core.auth.credentials.client_config import ClientConfigStore
from mas.core.auth.discovery.detector import AuthDetector
from mas.core.auth.protocols.oauth2.login_service import OAuth2LoginService
from mas.core.enums import ResourceCategory
from mas.elements.providers.mcp_server_client.identifiers import Identifier
from mas.elements.providers.mcp_server_client.transport.enums import McpTransportType

logger = logging.getLogger(__name__)

_MCP_INIT_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "unifai-probe", "version": "1.0"},
    },
}
_PROBE_TIMEOUT = 10.0


class ValidateConnectionInput(BaseActionInput):
    mcp_url: HttpUrl
    user_id: str = Field(default="")
    transport_type: McpTransportType = Field(default=McpTransportType.STREAMABLE_HTTP)
    additional_headers: Dict[str, Any] = Field(default_factory=dict)


class ValidateConnectionOutput(BaseActionOutput):
    is_reachable: bool = False
    authenticated: bool = False
    auth_required: bool = False
    forbidden: bool = False
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
    version = "3.0.0"
    tags = {"mcp", "validation", "connectivity"}
    elements = {(ResourceCategory.PROVIDER.value, Identifier.TYPE)}

    def __init__(
        self,
        token_lifecycle: Optional[TokenLifecycleService] = None,
        detector: Optional[AuthDetector] = None,
        login_service: Optional[OAuth2LoginService] = None,
        client_configs: Optional[ClientConfigStore] = None,
    ):
        super().__init__()
        self._tokens = token_lifecycle
        self._detector = detector
        self._login = login_service
        self._configs = client_configs

    def execute_sync(self, input_data, context=None):
        try:
            return super().execute_sync(input_data, context)
        except RuntimeError as e:
            return ValidateConnectionOutput(
                success=False, message=f"Connection failed: {e}", is_reachable=False,
            )

    async def execute(
        self,
        input_data: ValidateConnectionInput,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidateConnectionOutput:
        start = time.time()
        mcp_url = str(input_data.mcp_url).rstrip("/")
        user_id = input_data.user_id
        extra_headers = input_data.additional_headers or {}

        # 1. Probe
        status_code, resp_headers, elapsed = await self._probe(mcp_url, None, extra_headers)

        if status_code is None:
            return ValidateConnectionOutput(
                success=False, message="Server unreachable",
                is_reachable=False, response_time_ms=elapsed,
            )
        if 200 <= status_code < 300:
            return ValidateConnectionOutput(
                success=True, message=f"Connected ({elapsed:.0f}ms)",
                is_reachable=True, response_time_ms=elapsed,
            )
        if status_code == 403:
            return ValidateConnectionOutput(
                success=False, message="Authenticated but not authorised",
                status="forbidden", is_reachable=True, forbidden=True,
                response_time_ms=elapsed,
            )
        if status_code != 401:
            return ValidateConnectionOutput(
                success=False, message=f"Unexpected status {status_code}",
                is_reachable=True, response_time_ms=(time.time() - start) * 1000,
            )

        # 2. 401 — discover auth server
        server_id = ""
        scopes: List[str] = []
        if self._detector:
            detection = await self._detector.detect(mcp_url, resp_headers)
            if detection:
                server_id = detection.server_identifier
                scopes = detection.scopes_supported

        if not user_id:
            return ValidateConnectionOutput(
                success=True, message="Authentication required",
                status="auth_required", is_reachable=True, auth_required=True,
                server_identifier=server_id, scopes=scopes,
                response_time_ms=(time.time() - start) * 1000,
            )

        # 3. Check existing token
        if server_id and self._tokens:
            token = self._tokens.get_valid_token(user_id, server_id)
            if token:
                retry_code, _, retry_elapsed = await self._probe(mcp_url, token, extra_headers)
                if retry_code and 200 <= retry_code < 300:
                    return ValidateConnectionOutput(
                        success=True, message=f"Connected ({retry_elapsed:.0f}ms)",
                        status="authenticated", is_reachable=True, authenticated=True,
                        server_identifier=server_id, response_time_ms=retry_elapsed,
                    )

        # 4. No token — try to build login URL
        if server_id and self._configs and self._login:
            config = self._configs.find_by_server(user_id, server_id)
            if config:
                url = await self._login.build_login_url(
                    user_id, server_id, config.model_dump(),
                )
                if url:
                    return ValidateConnectionOutput(
                        success=True, message="Sign in required",
                        status="requires_consent", is_reachable=True,
                        auth_required=True, server_identifier=server_id,
                        authorization_url=url, scopes=config.scopes,
                        response_time_ms=(time.time() - start) * 1000,
                    )

        # 5. Can't build login URL
        return ValidateConnectionOutput(
            success=True, message="Authentication required",
            status="auth_required", is_reachable=True, auth_required=True,
            server_identifier=server_id, scopes=scopes,
            response_time_ms=(time.time() - start) * 1000,
        )

    @staticmethod
    async def _probe(
        mcp_url: str,
        access_token: Optional[str],
        extra_headers: Dict[str, Any],
    ) -> tuple:
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        if extra_headers:
            headers.update(extra_headers)

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
                resp = await client.post(mcp_url, json=_MCP_INIT_BODY, headers=headers)
                elapsed = (time.time() - start) * 1000
                return resp.status_code, dict(resp.headers), elapsed
        except Exception as exc:
            elapsed = (time.time() - start) * 1000
            logger.debug("MCP probe failed for %s: %s", mcp_url, exc)
            return None, {}, elapsed
