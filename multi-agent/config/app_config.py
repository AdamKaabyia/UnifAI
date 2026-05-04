from pydantic import AliasChoices, Field

from global_utils.config.config import SharedConfig


class AppConfig(SharedConfig):
    """
    Multi-agent service config.

    ``mongodb_ip`` defaults to loopback for local dev. Set ``MONGODB_IP`` / ``mongodb_ip``
    in the environment in Kubernetes or shared compose so pods reach the real host.
    """

    mongodb_ip: str = "127.0.0.1"

    mongo_db: str = "UnifAI"
    blueprint_coll: str = "blueprints"
    resources_coll: str = "resources"
    session_coll: str = "workflow_sessions"
    shares_coll: str = "shares"
    templates_coll: str = "templates"
    credentials_coll: str = "credentials"
    # Never name this field ``hostname``: pydantic-settings maps it to env ``HOSTNAME``,
    # which Linux/Kubernetes set to the machine/pod name and overrides ``.env`` — Flask
    # then binds off loopback and the Vite proxy (127.0.0.1:8002) never connects.
    bind_host: str = Field(
        default="0.0.0.0",
        validation_alias=AliasChoices("MAS_API_BIND_HOST", "BIND_HOST"),
    )
    port: str = "8002"
    version: str = "1.0.0"
    admin_allowed_users: list = []  # Populate with user_ids (usernames) to grant admin access
    secret_key: str = ""
    # Engine
    engine_name: str = "temporal"
    temporal_task_queue: str = "graph-engine"
    # Redis streaming tuning
    redis_stream_ttl: int = 3600
    redis_stream_block_ms: int = 5000
    redis_stream_batch_size: int = 50

    # Collaboration hub — Redis-backed multi-user session presence
    collaboration_presence_ttl: int = 300
    collaboration_edit_lock_ttl_sec: int = 180

    # Directory provider: "sso" (via Identity pod) or "" to disable
    directory_provider: str = ""
    directory_timeout: int = 10

    # Identity HTTP base for directory + teams HTTP APIs (optional override).
    # When empty, ``identity_host`` is used for ``SsoDirectoryClient`` and auth decorators.
    directory_sso_url: str = ""

    # MCP Auth
    mcp_auth_state_secret: str = ""
    identity_host: str = "http://localhost:13456"
    credential_encryption_key: str = ""
