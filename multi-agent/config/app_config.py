from global_utils.config.config import SharedConfig


class AppConfig(SharedConfig):
    mongo_db: str = "UnifAI"
    blueprint_coll: str = "blueprints"
    resources_coll: str = "resources"
    session_coll: str = "workflow_sessions"
    shares_coll: str = "shares"
    templates_coll: str = "templates"
    auth_tokens_coll: str = "auth_tokens"
    hostname: str = "0.0.0.0"
    port: str = "8002"
    version: str = "1.0.0"
    admin_allowed_users: list = []  # Populate with user_ids (usernames) to grant admin access
    # Engine
    engine_name: str = "temporal"
    temporal_task_queue: str = "graph-engine"
    # Redis streaming tuning
    redis_stream_ttl: int = 3600
    redis_stream_block_ms: int = 5000
    redis_stream_batch_size: int = 50
    # MCP Auth
    mcp_auth_state_secret: str = ""
    sso_callback_url: str = "http://localhost:13456/api/mcp-auth/callback"
    internal_service_token: str = "unifai-dev-internal-token"  # TODO: move to env var / secrets manager for production
