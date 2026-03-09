import pymongo
from config.app_config import AppConfig
from teams.repository.mongo_repository import MongoTeamRepository
from teams.service import TeamService
from global_utils.utils.singleton import SingletonMeta


class AppContainer(metaclass=SingletonMeta):
    def __init__(self, cfg: AppConfig):
        if getattr(self, "_initialized", False):
            return

        mongo_uri = f"mongodb://{cfg.mongodb_ip}:{cfg.mongodb_port}/"
        self.mongo_client = pymongo.MongoClient(mongo_uri)
        db = self.mongo_client[cfg.mongo_db]

        self.team_repo = MongoTeamRepository(db=db, coll_name=cfg.teams_coll)
        self.team_service = TeamService(repository=self.team_repo)

        self._initialized = True
