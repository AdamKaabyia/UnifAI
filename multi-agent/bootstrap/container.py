"""
Composition root — the outermost ring of the architecture.

This is the single place that knows about BOTH the domain hexagon (mas.*)
AND the concrete adapter implementations (outbound.*).  It wires ports
to adapters and assembles the full object graph.

No domain or adapter code should ever import this module.  Only entry
points (run/dev.py, run/wsgi.py, inbound/temporal/__main__.py, …)
create an AppContainer and pass it — or individual services from it —
into the layers that need them.
"""
from mas.catalog.element_registry import ElementRegistry
from mas.catalog.service import CatalogService
from mas.catalog.card_service import ElementCardService
from mas.blueprints.service import BlueprintService
from mas.blueprints.resolver import BlueprintResolver
from mas.session.building import WorkflowSessionFactory
from mas.session.management import UserSessionManager
from mas.session.execution import SessionLifecycle, ForegroundSessionRunner, SessionInputProjector
from mas.session.service import SessionService
from mas.resources.registry import ResourcesRegistry
from mas.resources.service import ResourcesService
from mas.graph.service import GraphService
from mas.graph.validation.service import GraphValidationService
from mas.actions.service import ActionsService
from mas.sharing.cloner import ShareCloner
from mas.sharing.service import ShareService
from mas.statistics.service import StatisticsService
from mas.validation.service import ElementValidationService
from mas.templates.service import TemplateService
from config.app_config import AppConfig

from outbound.mongo import (
    MongoBlueprintRepository,
    MongoSessionRepository,
    MongoResourceRepository,
    MongoShareRepository,
    MongoTemplateRepository,
)

from global_utils.utils.singleton import SingletonMeta
from global_utils.utils.util import get_redis_url


class AppContainer(metaclass=SingletonMeta):
    """
    Central composition root.  All wiring lives here:
      - reads collection names   from AppConfig
      - reads engine_name        from AppConfig
      - reads mongo_uri & db     from AppConfig
    """

    def __init__(self, cfg: AppConfig):
        if getattr(self, "_initialized", False):
            return

        self.element_registry = ElementRegistry()
        self.element_registry.auto_discover()

        self.actions_service = ActionsService()
        self.actions_service.auto_discover_actions()

        self.catalog_service = CatalogService(self.element_registry)

        self.graph_service = GraphService(self.element_registry)
        self.graph_validation_service = GraphValidationService(self.element_registry)

        self.validation_service = ElementValidationService(
            element_registry=self.element_registry
        )

        self.card_service = ElementCardService(
            element_registry=self.element_registry
        )

        self.blueprint_repo = MongoBlueprintRepository(
            db_name=cfg.mongo_db,
            coll_name=cfg.blueprint_coll
        )

        resource_registry = ResourcesRegistry(
            repo=MongoResourceRepository(
                cfg.mongodb_port,
                mongodb_ip=cfg.mongodb_ip,
                db_name=cfg.mongo_db,
                coll_name=cfg.resources_coll,
            ),
            bp_repo=self.blueprint_repo,
        )

        self.resources_service = ResourcesService(
            resource_registry=resource_registry,
            element_registry=self.element_registry,
            validation_service=self.validation_service,
            card_service=self.card_service,
        )

        self.blueprint_resolver = BlueprintResolver(
            resource_registry=resource_registry,
            element_registry=self.element_registry
        )

        self.blueprint_service = BlueprintService(
            self.blueprint_repo,
            resolver=self.blueprint_resolver,
            validation_service=self.validation_service,
            card_service=self.card_service,
        )

        self.session_factory = WorkflowSessionFactory(
            element_registry=self.element_registry,
            engine_name=cfg.engine_name
        )
        self.session_repo = MongoSessionRepository(
            mongodb_port=cfg.mongodb_port,
            mongodb_ip=cfg.mongodb_ip,
            db_name=cfg.mongo_db,
            collection_name=cfg.session_coll
        )
        self.session_manager = UserSessionManager(
            repository=self.session_repo,
            session_factory=self.session_factory,
            blueprint_service=self.blueprint_service
        )

        self.session_lifecycle = SessionLifecycle(repository=self.session_repo)
        self.input_projector = SessionInputProjector(repository=self.session_repo)

        self.channel_factory = self._create_channel_factory(cfg)

        foreground_runner = ForegroundSessionRunner(
            lifecycle=self.session_lifecycle,
            channel_factory=self.channel_factory,
        )

        background_submitter = self._create_background_submitter(cfg.engine_name)

        self.session_service = SessionService(
            manager=self.session_manager,
            foreground_runner=foreground_runner,
            input_projector=self.input_projector,
            background_submitter=background_submitter,
        )

        self.share_repo = MongoShareRepository(
            db_name=cfg.mongo_db,
            coll_name=cfg.shares_coll
        )
        self.share_cloner = ShareCloner(
            resources_registry=resource_registry,
            blueprint_service=self.blueprint_service,
            element_registry=self.element_registry
        )
        self.share_service = ShareService(
            share_repository=self.share_repo,
            cloner=self.share_cloner
        )

        self.statistics_service = StatisticsService(
            blueprint_service=self.blueprint_service,
            session_service=self.session_service,
            resources_service=self.resources_service
        )

        self.template_repo = MongoTemplateRepository(
            db_name=cfg.mongo_db,
            coll_name=cfg.templates_coll
        )
        self.template_service = TemplateService(
            repository=self.template_repo,
            element_registry=self.element_registry,
            blueprint_service=self.blueprint_service,
            resources_service=self.resources_service,
        )

        self._initialized = True

    @staticmethod
    def _create_channel_factory(cfg: AppConfig):
        redis_url = get_redis_url()
        if redis_url:
            from outbound.channels import RedisChannelFactory
            return RedisChannelFactory(
                redis_url=redis_url,
                stream_ttl=cfg.redis_stream_ttl,
                block_ms=cfg.redis_stream_block_ms,
                batch_size=cfg.redis_stream_batch_size,
            )
        from outbound.channels import LocalChannelFactory
        return LocalChannelFactory()

    @staticmethod
    def _create_background_submitter(engine_name: str):
        if engine_name == "temporal":
            from outbound.temporal.submitter import TemporalSessionSubmitter
            return TemporalSessionSubmitter()
        return None
