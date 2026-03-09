from global_utils.config.config import SharedConfig


class AppConfig(SharedConfig):
    mongo_db: str = "UnifAI"
    teams_coll: str = "teams"
    hostname: str = "0.0.0.0"
    port: str = "8004"
