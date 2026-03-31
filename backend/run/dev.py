from api.flask.flask_app import create_app
from config.app_config import AppConfig

if __name__ == '__main__':
    config = AppConfig.get_instance()
    app = create_app(config=config)
    app.run(host=config.hostname_local, port=config.port, debug=True)
