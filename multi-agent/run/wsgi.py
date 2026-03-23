"""WSGI callable for gunicorn: ``gunicorn run.wsgi:application``."""
from config.app_config import AppConfig
from bootstrap.container import AppContainer
from inbound.flask.flask_app import create_app

_cfg = AppConfig.get_instance()
_container = AppContainer(_cfg)
application = create_app(_container, config=_cfg)
