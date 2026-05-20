"""
Jira / Atlassian OAuth auth element — pre-configured with Atlassian's server identifier.
"""

from typing import Literal, Optional

from pydantic import Field

from mas.core.field_hints import ActionHint, HintType
from mas.elements.auths.common.base_config import AuthBaseConfig

_TYPE = "jira_oauth"


class JiraOAuthConfig(AuthBaseConfig):
    type: Literal[_TYPE] = _TYPE

    protocol_type: Literal["oauth2"] = Field(
        default="oauth2",
        description="Authentication protocol",
    )
    display_name: str = Field(
        default="Jira / Atlassian OAuth",
        description="Human-readable name",
    )
    server_identifier: str = Field(
        default="https://auth.atlassian.com",
        description="Atlassian auth server",
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
