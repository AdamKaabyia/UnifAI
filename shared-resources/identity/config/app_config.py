from global_utils.config.config import SharedConfig


class AppConfig(SharedConfig):

    # App Configuration
    app_name: str = "identity"
    hostname_local: str = "127.0.0.1"
    port: str = "13456"

    # Keycloak Configuration
    keycloak_base_url: str = "https://auth.redhat.com/auth"
    client_id: str = "TAG-001"
    client_secret: str = "e7CLFJT6mRhzAYa1G87wpgYKYjmrfqXK"
    keycloak_realm: str = "EmployeeIDP"
    version: str = "1.0.0"
    admin_allowed_users: list = []  # Populate with user_ids (usernames) to grant admin access

    frontend_url: str = "http://127.0.0.1:5000"    # session_cookie_secure=True
    backend_env: str = "development"

    # Redis Configuration
    redis_ip: str = "redis"
    redis_port: int = 6379
    redis_db: int = 1
    redis_password: str = 'Mc10vin!!'
    redis_decode_responses: bool = True
    redis_session_ttl: int = 3600