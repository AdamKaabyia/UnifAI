"""
OAuthClientConfig — generic auth element.

The auth element is a simple selector: "I want to authenticate with this server."
Client credentials (client_id, secret, endpoints) are stored separately
in the ServerConfigStore.
"""

from typing import Literal, Optional

from pydantic import Field

from mas.core.field_hints import ActionHint, HintType
from mas.elements.auths.common.base_config import AuthBaseConfig
from .identifiers import Identifier


class OAuthClientConfig(AuthBaseConfig):
    type: Literal[Identifier.TYPE] = Identifier.TYPE

    protocol_type: Literal["oauth2"] = Field(
        default="oauth2",
        description="Authentication protocol (oauth2)",
    )
    display_name: str = Field(
        description="Human-readable name (e.g. 'My Google Auth')",
    )
    server_identifier: str = Field(
        default="",
        description="Auth server issuer (e.g. https://accounts.google.com). "
                    "Leave empty for auto-detection.",
    )

    auth_status: Optional[str] = Field(
        default=None,
        description="Authentication status (managed by the system)",
        json_schema_extra=ActionHint(
            action_uid="auth.authenticate",
            hint_type=HintType.VALIDATE,
            field_mapping="status",
            dependencies={
                "server_identifier": "server_identifier",
            },
        ).to_hints(),
    )
