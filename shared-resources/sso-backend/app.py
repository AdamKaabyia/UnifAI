import os
import sys

# Add the parent directory of 'backend' (the root of the project) to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from endpoints import register_all_endpoints
from flask import Flask
from flask_cors import CORS
from global_utils.flask.request_rules import RequestRules
from utils.auth_manager import AuthManager
from models.user import UserRepository
from services.auth_service import AuthService
from services.profile_service import ProfileService
from config.app_config import AppConfig
from directory.factory import build_directory_provider

# Init FLASK
app = Flask(__name__)

config = AppConfig.get_instance()
app.secret_key = config.get('secret_key', os.urandom(24))
app.version = config.get("version", "1.0.0")
# Configure CORS to allow credentials
CORS(app, supports_credentials=True, origins=os.environ.get("FRONTEND_URL", "http://localhost:5000"))

# Initialize Keycloak SSO AuthManager for internal users
auth_manager = AuthManager(app)
app.extensions['auth_manager'] = auth_manager

# Initialize User Repository for local auth
user_repo = UserRepository(
    mongodb_ip=config.get('mongodb_ip', 'localhost'),
    mongodb_port=config.get('mongodb_port', '27017'),
    db_name="UnifAI",
    collection_name="local_users"
)

# Initialize directory provider (LDAP/Rover) — None when disabled
directory_provider = build_directory_provider(config)
app.extensions['directory_provider'] = directory_provider

# Initialize Services for local auth (SOLID pattern)
auth_service = AuthService(user_repo, directory_provider=directory_provider)
profile_service = ProfileService(user_repo)

# Register services in app extensions for endpoint access
app.extensions['auth_service'] = auth_service
app.extensions['profile_service'] = profile_service

register_all_endpoints(app)

# Init before_request/after_request rules
RequestRules(app)

if __name__ == '__main__':
    app.run(host=config.hostname_local, port=config.port, debug=True)