"""
Flask Application Factory.

Creates and configures the Flask application using hexagonal architecture.
HTTP adapters are registered as blueprints.

Usage:
    from bootstrap.flask_app import create_app
    
    app = create_app()
    app.run(host="0.0.0.0", port=5000)
"""
import os
import logging
from flask import Flask
from flask_cors import CORS

from config.app_config import AppConfig
from config.logging_config import LoggingConfig
from global_utils.flask.request_rules import RequestRules
from bootstrap.factories import build_auth_stack


def create_app() -> Flask:
    """
    Application factory for Flask app.
    
    Creates a Flask application with:
    - CORS configuration
    - Secret key
    - All HTTP endpoint blueprints registered
    - Request validation rules
    
    Returns:
        Configured Flask application
    """
    
    config = AppConfig.get_instance()

    #logging setup for app and all sub-modules.
    logging.basicConfig(
        level=LoggingConfig.log_level,
        format=LoggingConfig.log_format,
    )
    logger = logging.getLogger(config.app_name)

    app = Flask(config.app_name)
        
    # Application config
    app.secret_key = config.get("secret_key", os.urandom(24)) # this key is crucial to code and decode all cookies. and it should be taken from env.
    app.version = config.get("version", "1.0.0")
    
    # CORS
    CORS(
        app,
        supports_credentials=True,
        origins=os.environ.get("FRONTEND_URL", "http://localhost:5000"),
    )
    
    #build auth stack
    auth_manager = build_auth_stack(app, config)
    # redis_store = RedisKVStore(
    # host=config.redis_ip,
    # port=config.redis_port,
    # db=config.redis_db,
    # password=config.redis_password,
    # decode_responses=config.redis_decode_responses,
    # )
    # Initialize Authentication Manager
    # auth_manager = AuthManager(app, redis_store)

    # Store auth_manager in app extensions for easy access
    app.extensions['auth_manager'] = auth_manager
    # Register HTTP adapters (blueprints)
    _register_blueprints(app)
    
    # Request validation rules
    RequestRules(app)
    
    return app


def _register_blueprints(app: Flask) -> None:
    """Register all HTTP endpoint blueprints."""
    from adapters.inbound.flask.endpoints import register_all_endpoints
    register_all_endpoints(app)


app = create_app()
# ══════════════════════════════════════════════════════════════════════════════
# Development Entry Point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    config = AppConfig.get_instance()
    app.run(
        host=config.hostname_local,
        port=int(config.port),
        debug=True,
    )

