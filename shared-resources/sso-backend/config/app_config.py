from global_utils.config.config import SharedConfig


class AppConfig(SharedConfig):

    hostname_local: str = "0.0.0.0"
    port: str = "13456"

    # Keycloak Configuration
    keycloak_base_url: str = "0.0.0.0"
    client_id: str = ""
    client_secret: str = ""
    keycloak_realm: str = ""
    version: str = "1.0.0"
    admin_allowed_users: list = []  # Populate with user_ids (usernames) to grant admin access

    frontend_url: str = "http://localhost:5000"    # session_cookie_secure=True
    backend_env: str = "development"

