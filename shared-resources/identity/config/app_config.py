from global_utils.config.config import SharedConfig


class AppConfig(SharedConfig):

    # App Configuration
    app_name: str = "identity"
    hostname_local: str = "127.0.0.1"
    port: str = "13456"

    # Keycloak Configuration
    keycloak_base_url: str = ""
    client_id: str = "1"
    client_secret: str = ""
    keycloak_realm: str = ""
    version: str = "1.0.0"
    admin_allowed_users: list = []  # Populate with user_ids (usernames) to grant admin access

    frontend_url: str = "http://127.0.0.1:5000"    # session_cookie_secure=True
    backend_env: str = "development"

    # Redis Configuration
    redis_db: int = 1
    redis_password: str = ""
    redis_decode_responses: bool = True
    redis_session_ttl: int = 3600