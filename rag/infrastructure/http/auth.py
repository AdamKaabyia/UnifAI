"""RAG session-based authentication decorator.

Validates the Flask session cookie against the Redis server session.
Endpoints read the authenticated username from ``g.identity_session.username``.
"""
from flask import current_app, session

from global_utils.flask.decorators import require_identity_session

rag_require_session = require_identity_session(
    get_redis_store=lambda: current_app.extensions['redis_kv_store'],
)
