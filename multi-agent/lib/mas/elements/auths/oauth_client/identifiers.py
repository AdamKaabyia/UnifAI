from dataclasses import dataclass


class Identifier:
    TYPE = "oauth_client"


@dataclass(frozen=True)
class OAuthClientMeta:
    name: str = "OAuth Client"
    description: str = (
        "OAuth 2.x client credentials for authenticating with external services. "
        "Configure client ID, secret, endpoints, and scopes. "
        "Can be referenced by any element that needs authenticated access."
    )
    tags: tuple = ("auth", "oauth2", "credentials")


META = OAuthClientMeta()
