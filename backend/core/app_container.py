import logging
from typing import Optional

from pymongo import MongoClient

from admin_config.action_dispatcher import ActionDispatcher
from admin_config.repository.mongo_repository import MongoAdminConfigRepository
from admin_config.service import AdminConfigService
from admin_config.template import ADMIN_CONFIG_TEMPLATE
from config.app_config import AppConfig
from global_utils.utils.singleton import SingletonMeta
from global_utils.utils.util import get_mongo_url
from teams.providers.provider import TeamDirectoryProvider
from teams.repository.mongo_repository import MongoTeamRepository
from teams.service import TeamService

logger = logging.getLogger(__name__)

_DIRECTORY_PROVIDERS = {
    "ldap": "_build_ldap_provider",
}


class AppContainer(metaclass=SingletonMeta):
    """
    Central composition root for the platform backend.

    All wiring lives here:
      - owns the shared MongoClient (single connection pool)
      - reads collection names from AppConfig
      - owns the ActionDispatcher for server-side side-effects
      - builds the team directory provider selected by config
    """

    def __init__(self, cfg: AppConfig):
        if getattr(self, "_initialized", False):
            return

        mongo_client = MongoClient(get_mongo_url())
        db = mongo_client[cfg.mongo_db]

        self.admin_config_repo = MongoAdminConfigRepository(
            collection=db[cfg.admin_config_coll],
        )

        self.action_dispatcher = ActionDispatcher(
            service_urls={"rag": cfg.rag_url},
        )

        self.admin_config_service = AdminConfigService(
            repository=self.admin_config_repo,
            template=ADMIN_CONFIG_TEMPLATE,
            action_dispatcher=self.action_dispatcher,
        )

        teams_db = mongo_client["UnifAI"]
        self.team_repo = MongoTeamRepository(db=teams_db, coll_name=cfg.teams_coll)

        directory_provider = self._build_directory_provider(cfg)
        self.team_service = TeamService(
            repository=self.team_repo,
            directory_provider=directory_provider,
        )

        self._initialized = True

    # ────────────────── directory-provider factory ────────────────────

    @staticmethod
    def _build_directory_provider(cfg: AppConfig) -> Optional[TeamDirectoryProvider]:
        provider_name = cfg.team_directory_provider.strip().lower()
        if not provider_name:
            return None

        builder_name = _DIRECTORY_PROVIDERS.get(provider_name)
        if not builder_name:
            raise ValueError(
                f"Unknown team_directory_provider: '{provider_name}'. "
                f"Supported: {', '.join(_DIRECTORY_PROVIDERS)}"
            )

        builder = getattr(AppContainer, builder_name)
        return builder(cfg)

    @staticmethod
    def _build_ldap_provider(cfg: AppConfig) -> TeamDirectoryProvider:
        from teams.providers.ldap import LdapDirectoryProvider, LdapConfig

        if not cfg.team_directory_url:
            raise ValueError(
                "team_directory_url is required when team_directory_provider='ldap'"
            )
        if not cfg.team_directory_ldap_user_base_dn:
            raise ValueError(
                "team_directory_ldap_user_base_dn is required when "
                "team_directory_provider='ldap'"
            )

        ldap_cfg = LdapConfig(
            url=cfg.team_directory_url,
            user_base_dn=cfg.team_directory_ldap_user_base_dn,
            bind_dn=cfg.team_directory_ldap_bind_dn,
            bind_password=cfg.team_directory_ldap_bind_password,
            skip_tls_verify=not cfg.team_directory_verify_ssl,
            timeout_seconds=cfg.team_directory_timeout,
        )
        logger.info("Team directory provider: ldap (%s)", cfg.team_directory_url)
        return LdapDirectoryProvider(config=ldap_cfg)
