from typing import Any, Dict, Literal, List, Optional
from .identifiers import Identifier
from pydantic import Field, HttpUrl
from mas.elements.providers.common.base_config import ProviderBaseConfig
from mas.core.field_hints import ActionHint, HiddenHint, HintType, SelectionType
from mas.core.ref.models import AuthRef
from .transport.enums import McpTransportType


class McpProviderConfig(ProviderBaseConfig):
    """
    Connects to a Model-Context-Protocol service via SSE or Streamable HTTP transport.
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
                "transport_type": "transport_type",
                "additional_headers": "additional_headers",
            }
        ).to_hints()
    )
    auth: Optional[AuthRef] = Field(
        default=None,
        description="Reference to an auth element for authenticated connections",
    )
    server_identifier: str = Field(
        default="",
        description="Auth server issuer discovered by validate_connection (e.g. https://accounts.google.com)",
        json_schema_extra=HiddenHint(reason="Set automatically by connection validation").to_hints()
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
                "transport_type": "transport_type",
                "additional_headers": "additional_headers",
            }
        ).to_hints()
    )
