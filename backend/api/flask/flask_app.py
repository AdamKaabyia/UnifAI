import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from flask import Flask
from flask_cors import CORS
from config.app_config import AppConfig
from core.app_container import AppContainer
from api.flask.endpoints import register_all_endpoints


def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {
        "origins": "*",
        "supports_credentials": True,
    }})

    cfg = AppConfig()
    container = AppContainer(cfg)
    app.container = container

    register_all_endpoints(app)

    return app
