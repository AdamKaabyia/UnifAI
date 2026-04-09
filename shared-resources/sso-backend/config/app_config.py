from global_utils.config.config import SharedConfig


class AppConfig(SharedConfig):

    hostname_local: str = "0.0.0.0"
    port: str = "13456"

    # Keycloak Configuration
    keycloak_base_url: str = "https://auth.stage.redhat.com/auth"
    client_id: str = "TAG-001"
    client_secret: str = "a0a82b17-e7e7-49c6-ad1c-3d03c79ff4fd"
    keycloak_realm: str = "EmployeeIDP"
    version: str = "1.0.0"
    admin_allowed_users: list = []

    frontend_url: str = "http://localhost:5000"
    backend_env: str = "development"

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

