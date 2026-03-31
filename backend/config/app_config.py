from global_utils.config.config import SharedConfig


class AppConfig(SharedConfig):
    mongo_db: str = "config"
    admin_config_coll: str = "admin_config"
    hostname_local: str = "0.0.0.0"
    port: str = "8005"
    version: str = "1.0.0"
    admin_allowed_users: list = []
    rag_url: str = "http://localhost:13457"
