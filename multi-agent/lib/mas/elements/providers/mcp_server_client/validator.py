"""
elements/providers/mcp_server_client/validator.py

Validator for MCP Provider — lightweight HTTP probe (no MCP SDK).

Uses the same JSON-RPC initialize probe as ValidateConnectionAction
so that 401/403 responses are handled cleanly instead of crashing
the MCP SDK's async generator teardown.
"""

import time
import logging
from typing import Any, Dict, List

import httpx
from global_utils.utils.async_bridge import get_async_bridge
from mas.elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from mas.elements.providers.mcp_server_client.config import McpProviderConfig

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


class McpProviderValidator(BaseElementValidator):
    """
    Validates MCP Provider configuration via lightweight HTTP probe.

    Sends a JSON-RPC initialize request directly with httpx.
    Handles auth-related responses (401/403) gracefully.
    """

    def validate(
        self,
        config: McpProviderConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        messages: List[ValidationMessage] = []

        try:
            with get_async_bridge() as bridge:
                bridge.run(self._probe_connection(config, context, messages))
        except Exception as e:
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                f"Connection failed: {e}",
                field="mcp_url",
            ))

        return self._build_report(messages=messages)

    async def _probe_connection(
        self,
        config: McpProviderConfig,
        context: ValidationContext,
        messages: List[ValidationMessage],
    ) -> None:
        mcp_url = str(config.mcp_url).rstrip("/")
        headers: Dict[str, Any] = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if config.additional_headers:
            headers.update(config.additional_headers)

        timeout = min(context.timeout_seconds, 10.0)
        start = time.time()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    mcp_url, json=_MCP_INIT_BODY, headers=headers,
                )
            elapsed = (time.time() - start) * 1000
        except httpx.TimeoutException:
            messages.append(self._error(
                ValidationCode.NETWORK_TIMEOUT.value,
                f"Connection timed out after {timeout}s",
                field="mcp_url",
            ))
            return
        except Exception as exc:
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                f"Connection failed: {exc}",
                field="mcp_url",
            ))
            return

        if 200 <= resp.status_code < 300:
            messages.append(self._info(
                "CONNECTION_OK",
                f"Connected to MCP server at {config.mcp_url} ({elapsed:.0f}ms)",
                field="mcp_url",
            ))
        elif resp.status_code == 401:
            messages.append(self._warning(
                "AUTH_REQUIRED",
                "Server requires authentication — sign in via the MCP connection panel",
                field="mcp_url",
            ))
        elif resp.status_code == 403:
            messages.append(self._error(
                ValidationCode.INVALID_CREDENTIALS.value,
                "Authenticated but not authorized — check your scopes or contact the server administrator",
                field="mcp_url",
            ))
        else:
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                f"Server returned unexpected status {resp.status_code}",
                field="mcp_url",
            ))
