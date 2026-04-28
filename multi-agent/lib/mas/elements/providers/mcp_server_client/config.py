from typing import Any, Dict, Literal, List, Optional
from enum import Enum
from .identifiers import Identifier
from pydantic import Field, HttpUrl
from mas.elements.providers.common.base_config import ProviderBaseConfig
from mas.core.field_hints import (
    ActionHint, HintType, SelectionType,
    SecretHint, ConditionalHint, combine_hints,
)
from .transport.enums import McpTransportType


class McpAuthMethod(str, Enum):
    """How the user authenticates to the MCP server."""
    NONE = "none"
    SIGN_IN = "sign_in"
    ACCESS_TOKEN = "access_token"


class McpProviderConfig(ProviderBaseConfig):
    """
    Connects to a Model-Context-Protocol service via SSE or Streamable HTTP transport.

    Authentication is handled through ``core/auth``.  The user can either
    complete an OAuth sign-in flow or paste a bearer token / API key.
    Both paths persist a ``StoredCredential`` in the token store keyed by
    ``(user_id, server_identifier)`` — the provider retrieves it at runtime
    via ``AuthService.bind_lazy()``.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    transport_type: McpTransportType = Field(
        default=McpTransportType.STREAMABLE_HTTP,
        description="Transport protocol to use for MCP server communication (sse or streamable http)"
    )
    mcp_url: HttpUrl = Field(
        description="MCP server endpoint URL",
        json_schema_extra=ActionHint(
            action_uid="mcp.validate_connection",
            hint_type=HintType.VALIDATE,
            field_mapping="is_reachable",
            dependencies={
                "mcp_url": "mcp_url",
                "bearer_token": "bearer_token",
                "transport_type": "transport_type",
                "additional_headers": "additional_headers",
            }
        ).to_hints()
    )
    auth: Optional[str] = Field(
        default=None,
        exclude=True,
        description="Deprecated — auth is now handled via core/auth token store",
    )
    auth_method: McpAuthMethod = Field(
        default=McpAuthMethod.NONE,
        description="Authentication method for this MCP server",
    )
    server_identifier: str = Field(
        default="",
        description="Auth server issuer (set automatically by connection validation)",
    )
    bearer_token: Optional[str] = Field(
        default=None,
        description="API key or bearer token",
        json_schema_extra=combine_hints(
            SecretHint(allow_reveal=True),
            ConditionalHint(visible_when={"auth_method": "access_token"}),
        ),
    )
    additional_headers: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional HTTP headers to include in MCP server requests"
    )
    tool_names: Optional[List[str]] = Field(
        default_factory=list,
        description="List of specific tool names to use from the MCP server",
        json_schema_extra=ActionHint(
            action_uid="mcp.get_tools_names",
            hint_type=HintType.POPULATE,
            selection_type=SelectionType.MANUAL,
            field_mapping="tool_names",
            multi_select=True,
            dependencies={
                "mcp_url": "mcp_url",
                "bearer_token": "bearer_token",
                "transport_type": "transport_type",
                "additional_headers": "additional_headers",
                "server_identifier": "server_identifier",
            }
        ).to_hints()
    )
