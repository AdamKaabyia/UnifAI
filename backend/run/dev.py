import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.flask.flask_app import create_app
from config.app_config import AppConfig

if __name__ == '__main__':
    config = AppConfig.get_instance()
    app = create_app(config=config)
    app.run(host="0.0.0.0", port=config.port, debug=True)
