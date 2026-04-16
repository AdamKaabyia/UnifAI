from mas.core.enums import ResourceCategory
from mas.elements.common.base_element_spec import BaseElementSpec
from mas.elements.auths.oauth_client.oauth_client_factory import OAuthClientFactory
from ..config import GitHubOAuthConfig


class GitHubOAuthElementSpec(BaseElementSpec):
    category = ResourceCategory.AUTH
    type_key = "github_oauth"
    name = "GitHub OAuth"
    description = (
        "Pre-configured OAuth 2.0 client for GitHub. "
        "Provide your OAuth App Client ID and Secret from GitHub Settings > Developer settings."
    )
    config_schema = GitHubOAuthConfig
    factory_cls = OAuthClientFactory
    tags = ["auth", "oauth2", "github"]
