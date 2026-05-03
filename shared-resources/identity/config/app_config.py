from global_utils.config.config import SharedConfig


class AppConfig(SharedConfig):

    # App Configuration
    app_name: str = "identity"
    hostname_local: str = "0.0.0.0"
    port: str = "13456"
    secret_key: str = ""

    # Keycloak Configuration
    keycloak_base_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    keycloak_realm: str = ""
    version: str = "1.0.0"
    admin_allowed_users: list = []  # Populate with user_ids (usernames) to grant admin access

    frontend_url: str = "http://localhost:5000"    
    backend_env: str = "development"

    # Multi-agent connection
    multiagent_host: str = "localhost"
    multiagent_port: str = "8002"

    # Session Configuration
    session_cookie_secure: bool = True
    session_cookie_http_only: bool = True
    session_cookie_samesite: str = "None"
    permanent_session_lifetime: int = 10
