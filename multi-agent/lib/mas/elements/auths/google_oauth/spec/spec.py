from mas.core.enums import ResourceCategory
from mas.elements.common.base_element_spec import BaseElementSpec
from mas.elements.auths.oauth_client.oauth_client_factory import OAuthClientFactory
from ..config import GoogleOAuthConfig


class GoogleOAuthElementSpec(BaseElementSpec):
    category = ResourceCategory.AUTH
    type_key = "google_oauth"
    name = "Google OAuth"
    description = (
        "Pre-configured OAuth 2.0 client for Google APIs. "
        "Provide your Client ID and Secret from Google Cloud Console."
    )
    config_schema = GoogleOAuthConfig
    factory_cls = OAuthClientFactory
    tags = ["auth", "oauth2", "google"]
