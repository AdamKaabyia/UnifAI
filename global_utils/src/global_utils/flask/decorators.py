"""
Flask decorators for access control.

Pluggable so each app can supply its own way to get the current user
and to check admin status (e.g. from config, DB, or admin config service).
"""
from functools import wraps

from flask import jsonify, request, current_app


def require_admin_access(get_current_user, is_admin):
    """
    Decorator factory: require admin access for an endpoint.

    Each app supplies:
      - get_current_user(request) -> str | None
        Return the current user identifier (e.g. username or user_id), or None if unknown.
      - is_admin(user_id: str) -> bool
        Return True if the user is an admin. Can use current_app inside.

    Returns:
        401 Unauthorized if no current user.
        403 Forbidden if the user is not an admin.
        500 on unexpected errors (with error_type ACCESS_CONTROL_ERROR).
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                user_id = get_current_user(request)
                if not user_id:
                    return jsonify({
                        "error": "Access denied: user identification is required",
                        "error_type": "AUTHENTICATION_REQUIRED",
                    }), 401
                if not is_admin(user_id):
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
    return decorator
