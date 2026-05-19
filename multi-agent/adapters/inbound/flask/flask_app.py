from flask import Flask
from config.app_config import AppConfig
from .endpoints import register_all_endpoints
from flask_cors import CORS
from global_utils.flask.request_rules import RequestRules
from global_utils.flask.decorators import configure_identity_base
import os


def create_app(container, config: AppConfig = None) -> Flask:
    """
    Application factory.

    Receives a fully-wired AppContainer from the entry point.
    This adapter never creates the container itself — it only consumes it.
    """
    config = config or AppConfig.get_instance()
    app = Flask(__name__)
    app.version = config.get("version", "1.0.0")
    app.secret_key = config.get("secret_key", os.urandom(24))
    app.config["admin_allowed_users"] = config.admin_allowed_users

    # Register the Identity pod base URL with the auth decorators so they can
    # call Identity's SERVICE API (teams.list, etc.) without reading it from
    # Flask's app.config.  Any API that requires the identity base belongs on
    # the Identity pod and is consumed by MAS via the outbound service client.
    identity_base = (config.directory_sso_url or config.identity_host or "").rstrip("/")
    configure_identity_base(identity_base)
    app.config["require_auth_header"] = config.require_auth_header or bool(identity_base)

    CORS(app, resources={r"/api/*": {"origins": "*",
                                     "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                                     "allow_headers": ["Content-Type", "Authorization",
                                                       "X-Authenticated-User"],
                                     "supports_credentials": True}})

    app.container = container
    register_all_endpoints(app)
    RequestRules(app)

    return app
