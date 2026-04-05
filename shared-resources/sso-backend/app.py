import os
import sys

# Add the parent directory of 'backend' (the root of the project) to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from endpoints import register_all_endpoints
from flask import Flask
from flask_cors import CORS
from global_utils.flask.request_rules import RequestRules
from utils.auth_manager import AuthManager
from config.app_config import AppConfig
from adapters.redis.redis_kv_store import RedisKVStore


# Init FLASK
app = Flask(__name__)

config = AppConfig.get_instance()
app.secret_key = config.get('secret_key', os.urandom(24))
app.version = config.get("version", "1.0.0")
# Configure CORS to allow credentials
CORS(app, supports_credentials=True, origins=os.environ.get("FRONTEND_URL", "http://localhost:5000"))

redis_store = RedisKVStore(
    host=config.redis_host,
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