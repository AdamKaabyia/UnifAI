from typing import Any, Dict, Literal, List, Optional
from enum import Enum
from .identifiers import Identifier
from pydantic import Field, HttpUrl
from mas.elements.providers.common.base_config import ProviderBaseConfig
from mas.core.field_hints import (
    ActionHint, HintType, SelectionType,
    SecretHint, AuthHint, HiddenHint, ConditionalHint, combine_hints,
)
from .transport.enums import McpTransportType


class McpAuthMethod(str, Enum):
    """How the user authenticates to the MCP server."""
    ACCESS_TOKEN = "access_token"
    SIGN_IN = "sign_in"


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
                "auth_method": "auth_method",
                "transport_type": "transport_type",
                "additional_headers": "additional_headers",
                "server_identifier": "server_identifier",
                "scheme_type": "scheme_type",
            }
        ).to_hints()
    )
    auth_method: McpAuthMethod = Field(
        default=McpAuthMethod.ACCESS_TOKEN,
        description="Authentication method for this MCP server",
    )
    server_identifier: str = Field(
        default="",
        description="Auth server issuer (set automatically by connection validation)",
        json_schema_extra=HiddenHint(reason="Set automatically by connection validation").to_hints(),
    )
    scheme_type: str = Field(
        default="",
        description="Auth scheme type (set automatically by connection validation)",
        json_schema_extra=HiddenHint(reason="Set automatically by auth detection").to_hints(),
    )
    sign_in: Optional[str] = Field(
        default=None,
        exclude=True,
        description="Sign in to authenticate with this MCP server",
        json_schema_extra=combine_hints(
            ConditionalHint(visible_when={"auth_method": "sign_in"}),
            AuthHint(
                action_uid="auth.authenticate",
                dependencies={
                    "server_identifier": "server_identifier",
                },
            ),
        ),
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
    def on_pre_save(self, user_id: str, **services) -> None:
        """Persist bearer_token to the credential store and clear it from config.

        Called by ``ResourcesService`` on save so that API-key credentials
        follow the same store-based path as OAuth credentials at runtime.
        """
        auth_service = services.get("auth_service")
        if not self.bearer_token or self.auth_method != McpAuthMethod.ACCESS_TOKEN or not auth_service:
            return

        from mas.core.auth.credentials.models import StoredCredential, TokenStatus

        server_id = str(self.mcp_url)
        auth_service.save_credential(StoredCredential(
            user_id=user_id,
            server_identifier=server_id,
            access_token=self.bearer_token,
            scheme_type="api_key",
            status=TokenStatus.ACTIVE,
            expires_at=None,
        ))

        object.__setattr__(self, "server_identifier", server_id)
        object.__setattr__(self, "scheme_type", "api_key")
        object.__setattr__(self, "bearer_token", None)

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
