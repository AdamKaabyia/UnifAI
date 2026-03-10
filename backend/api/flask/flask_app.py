import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from flask import Flask
from flask_cors import CORS
from config.app_config import AppConfig
from core.app_container import AppContainer
from .endpoints import register_all_endpoints


def create_app(config: AppConfig = None) -> Flask:
    config = config or AppConfig.get_instance()
    app = Flask(__name__)

    CORS(app, resources={r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True,
    }})

    container = AppContainer(config)
    app.container = container

    register_all_endpoints(app)

    return app
