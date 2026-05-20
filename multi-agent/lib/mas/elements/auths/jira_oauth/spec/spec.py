from mas.core.enums import ResourceCategory
from mas.elements.common.base_element_spec import BaseElementSpec
from mas.elements.auths.oauth_client.oauth_client_factory import OAuthClientFactory
from ..config import JiraOAuthConfig


class JiraOAuthElementSpec(BaseElementSpec):
    category = ResourceCategory.AUTH
    type_key = "jira_oauth"
    name = "Jira / Atlassian OAuth"
    description = (
        "Pre-configured OAuth 2.0 (3LO) client for Jira and Atlassian Cloud. "
        "Provide your Client ID and Secret from the Atlassian Developer Console."
    )
    config_schema = JiraOAuthConfig
    factory_cls = OAuthClientFactory
    tags = ["auth", "oauth2", "jira", "atlassian"]
