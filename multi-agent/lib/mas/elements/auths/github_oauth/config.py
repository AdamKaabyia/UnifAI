"""
GitHub OAuth auth element — pre-configured with GitHub's server identifier.
"""

from typing import Literal, Optional

from pydantic import Field

from mas.core.field_hints import ActionHint, HintType
from mas.elements.auths.common.base_config import AuthBaseConfig

_TYPE = "github_oauth"


class GitHubOAuthConfig(AuthBaseConfig):
    type: Literal[_TYPE] = _TYPE

    protocol_type: Literal["oauth2"] = Field(
        default="oauth2",
        description="Authentication protocol",
    )
    display_name: str = Field(
        default="GitHub OAuth",
        description="Human-readable name",
    )
    server_identifier: str = Field(
        default="https://github.com",
        description="GitHub auth server",
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
