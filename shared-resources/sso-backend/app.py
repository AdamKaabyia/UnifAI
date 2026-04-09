import os
import sys
import logging

# Add the parent directory of 'sso-backend' to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient

from endpoints import register_all_endpoints
from flask import Flask
from flask_cors import CORS
from global_utils.flask.request_rules import RequestRules
from global_utils.utils.util import get_mongo_url, get_redis_url
from utils.auth_manager import AuthManager
from utils.user_groups_cache import UserGroupsCache
from config.app_config import AppConfig
from directory.factory import build_directory_provider
from teams.repository.mongo_repository import MongoTeamRepository
from teams.service import TeamService

logger = logging.getLogger(__name__)

# Init FLASK
app = Flask(__name__)

config = AppConfig.get_instance()
app.secret_key = config.get('secret_key', os.urandom(24))
app.version = config.get("version", "1.0.0")
# Configure CORS to allow credentials
CORS(app, supports_credentials=True, origins=os.environ.get("FRONTEND_URL", "http://localhost:5000"))

# Initialize Authentication Manager
auth_manager = AuthManager(app)
app.extensions['auth_manager'] = auth_manager

# ── Redis (optional — for caching user ROVER groups) ──────────────────
redis_url = get_redis_url()
user_groups_cache = None
if redis_url:
    try:
        import redis
        redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
        user_groups_cache = UserGroupsCache(
            redis_client, ttl=config.user_groups_cache_ttl,
        )
        logger.info("Redis connected for user-groups cache (%s)", redis_url)
    except Exception as e:
        logger.warning("Redis unavailable — user-groups cache disabled: %s", e)
app.extensions['user_groups_cache'] = user_groups_cache

# ── Directory + Team wiring ───────────────────────────────────────────
mongo_client = MongoClient(get_mongo_url())
teams_db = mongo_client[config.mongo_db]
team_repo = MongoTeamRepository(db=teams_db, coll_name=config.teams_coll)
directory_provider = build_directory_provider(config)
team_service = TeamService(repository=team_repo, directory_provider=directory_provider)
app.extensions['team_service'] = team_service

register_all_endpoints(app)

# Init before_request/after_request rules
RequestRules(app)

if __name__ == '__main__':
    app.run(host=config.hostname_local, port=config.port, debug=True)