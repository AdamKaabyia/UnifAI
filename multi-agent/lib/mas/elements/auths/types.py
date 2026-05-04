"""
Discriminated union of all auth element config types.

Used by :class:`BlueprintSpec` for deserialization.
"""

from typing import Union

from .oauth_client.config import OAuthClientConfig
from .google_oauth.config import GoogleOAuthConfig
from .github_oauth.config import GitHubOAuthConfig
from .jira_oauth.config import JiraOAuthConfig

AuthSpec = Union[
    OAuthClientConfig,
    GoogleOAuthConfig,
    GitHubOAuthConfig,
    JiraOAuthConfig,
]
