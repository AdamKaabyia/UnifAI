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

    # MongoDB — teams collection
    mongo_db: str = "UnifAI"
    teams_coll: str = "teams"

    # Directory provider (e.g. "ldap" or "" to disable)
    directory_provider: str = ""
    directory_url: str = ""
    directory_timeout: int = 10
    directory_verify_ssl: bool = True

    # LDAP-specific settings (used when directory_provider="ldap")
    directory_ldap_user_base_dn: str = "ou=users,dc=redhat,dc=com"
    directory_ldap_group_base_dn: str = "ou=adhoc,ou=managedGroups,dc=redhat,dc=com"
    directory_ldap_group_object_class: str = "groupOfUniqueNames,rhatRoverGroup"
    directory_ldap_group_member_attr: str = "uniqueMember"
    directory_ldap_bind_dn: str = ""
    directory_ldap_bind_password: str = ""

    # User-groups cache TTL (seconds). Groups are fetched on login and
    # cached in Redis so we don't hit LDAP on every request.
    user_groups_cache_ttl: int = 3600
