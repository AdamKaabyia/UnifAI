"""
Decorators for Flask endpoints.

Auth / identity decorators live in ``global_utils.flask.decorators`` so that
any service (MAS, RAG, …) can consume them without duplication.  This module
re-exports them for backward-compatible imports and adds the MAS-specific
``require_admin_access`` that gates analytics endpoints via the
``admin_allowed_users`` config list.
"""
from functools import wraps

from flask import current_app, jsonify, request

from global_utils.flask.decorators import (  # noqa: F401  (re-exports)
    _fetch_team_ids_from_identity,
    _identity_service_base,
    _is_team_member,
    _resolve_team_id_for_member,
    with_authenticated_user,
    with_identity,
    with_require_identity_authorization,
)


def require_admin_access(f):
    """Decorator that gates an endpoint to users listed in ``admin_allowed_users``.

    Reads ``userId`` from kwargs (injected by ``@from_query``) or from the
    ``userId`` / ``user_id`` query parameter.

    Returns:
        403 when ``admin_allowed_users`` is empty (Analytics disabled).
        403 when the user is not in the allow-list.
        401 when ``userId`` is missing.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            admin_allowed_users = current_app.config.get("admin_allowed_users", [])

            if not admin_allowed_users:
                return jsonify({
                    "error": "Access denied: Analytics is not enabled",
                    "error_type": "FEATURE_DISABLED",
                }), 403

            user_id = (
                kwargs.get("user_id")
                or kwargs.get("userId")
                or request.args.get("user_id")
                or request.args.get("userId")
            )

            if not user_id:
                return jsonify({
                    "error": "Access denied: user_id is required",
                    "error_type": "AUTHENTICATION_REQUIRED",
                }), 401

            if user_id not in admin_allowed_users:
                return jsonify({
                    "error": "Access denied: insufficient permissions",
                    "error_type": "ACCESS_DENIED",
                }), 403

            return f(*args, **kwargs)

        except Exception as e:
            return jsonify({
                "error": f"Access control error: {str(e)}",
                "error_type": "ACCESS_CONTROL_ERROR",
            }), 500

    return decorated_function
