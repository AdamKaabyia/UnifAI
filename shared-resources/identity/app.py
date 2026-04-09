import os
import sys
import logging

# Add the parent directory of 'backend' (the root of the project) to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.logging_config import LoggingConfig
from adapters.inbound.flask.endpoints import register_all_endpoints
from flask import Flask
from flask_cors import CORS
from global_utils.flask.request_rules import RequestRules
from utils.auth_manager import AuthManager
from config.app_config import AppConfig
from adapters.outbound.redis.redis_kv_store import RedisKVStore

# configuration setup
config = AppConfig.get_instance()

#logging setup for app and all sub-modules.
logging.basicConfig(
    level=LoggingConfig.log_level,
    format=LoggingConfig.log_format,
)
logger = logging.getLogger(config.app_name)

# flask app setup
app = Flask(config.app_name)


app.secret_key = config.get('secret_key', os.urandom(24))
app.version = config.get("version", "1.0.0")

# Configure CORS to allow credentials
CORS(app, supports_credentials=True, origins=os.environ.get("FRONTEND_URL", "http://localhost:5000"))

redis_store = RedisKVStore(
    host=config.redis_ip,
    port=config.redis_port,
    db=config.redis_db,
    password=config.redis_password,
    decode_responses=config.redis_decode_responses,
)
# Initialize Authentication Manager
auth_manager = AuthManager(app, redis_store)

# Store auth_manager in app extensions for easy access
app.extensions['auth_manager'] = auth_manager

register_all_endpoints(app)

# Init before_request/after_request rules
RequestRules(app)

if __name__ == '__main__':
    app.run(host=config.hostname_local, port=config.port, debug=True)