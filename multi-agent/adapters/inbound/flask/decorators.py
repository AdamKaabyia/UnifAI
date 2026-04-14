"""
Decorators for Flask endpoints.
"""
import logging
from functools import wraps
from flask import jsonify, request, current_app

import requests as http_requests

from inbound.flask.identity_helpers import resolve_identity

logger = logging.getLogger(__name__)


def require_admin_access(f):
    """
    Decorator to require admin access for an endpoint.
    
    Checks if the user_id (from query params) is in admin_allowed_users list.
    If admin_allowed_users is empty, denies all access (Analytics is disabled).
    
    The decorator extracts user_id from:
    - Query parameter: 'userId' or 'user_id'
    - Function kwargs: 'user_id' or 'userId' (if passed by @from_query)
    
    Returns:
        403 Forbidden if admin_allowed_users is empty (Analytics disabled).
        403 Forbidden if user is not in admin_allowed_users list.
        401 Unauthorized if user_id is missing.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            admin_allowed_users = current_app.config.get("admin_allowed_users", [])
            
            if not admin_allowed_users:
                return jsonify({
                    "error": "Access denied: Analytics is not enabled",
                    "error_type": "FEATURE_DISABLED"
                }), 403
            
            user_id = kwargs.get("user_id") or kwargs.get("userId") or request.args.get("user_id") or request.args.get("userId")
            
            if not user_id:
                return jsonify({
                    "error": "Access denied: user_id is required",
                    "error_type": "AUTHENTICATION_REQUIRED"
                }), 401
            
            if user_id not in admin_allowed_users:
                return jsonify({
                    "error": "Access denied: insufficient permissions",
                    "error_type": "ACCESS_DENIED"
                }), 403
            
            return f(*args, **kwargs)
            
        except Exception as e:
            return jsonify({
                "error": f"Access control error: {str(e)}",
                "error_type": "ACCESS_CONTROL_ERROR"
            }), 500
    
    return decorated_function


def require_identity_authorization(f):
    """Validate that the caller is authorized for the claimed identity.

    Reads ``X-Authenticated-User`` from the request header (set by the UI).
    For **user** identity: the claimed ``userId`` must match the header.
    For **team** identity: the authenticated user must be a member of the
    claimed team (verified via the SSO backend's teams API).

    Skipped when the header is absent (allows direct/internal calls) or
    when no ``directory_sso_url`` is configured.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        authenticated_user = request.headers.get("X-Authenticated-User", "").strip()
        if not authenticated_user:
            return f(*args, **kwargs)

        identity_type = (
            kwargs.get("identity_type")
            or request.args.get("identityType")
            or (request.get_json(silent=True) or {}).get("identityType")
            or "user"
        )

        if identity_type != "team":
            return f(*args, **kwargs)

        claimed_id = (
            kwargs.get("user_id")
            or request.args.get("userId")
            or (request.get_json(silent=True) or {}).get("userId")
            or ""
        )

        if not claimed_id:
            return f(*args, **kwargs)

        if not _is_team_member(authenticated_user, claimed_id):
            return jsonify({
                "error": "Access denied: you are not a member of this team",
                "error_type": "TEAM_ACCESS_DENIED",
            }), 403

        return f(*args, **kwargs)

    return decorated_function


def _is_team_member(username: str, team_id: str) -> bool:
    """Check team membership via the SSO backend's ``teams.list`` endpoint.

    Fails **closed** (denies access) when the SSO backend is configured but
    unreachable or returns an error.  Only allows access without a check when
    no ``directory_sso_url`` is configured at all (e.g. local dev).
    """
    sso_url = current_app.config.get("directory_sso_url", "")
    if not sso_url:
        return True

    try:
        resp = http_requests.get(
            f"{sso_url}/api/teams/teams.list",
            params={"userId": username},
            timeout=5,
        )
        if resp.status_code != 200:
            logger.warning("Team membership check failed (HTTP %d) — denying access", resp.status_code)
            return False

        teams = resp.json().get("teams", [])
        return any(t.get("team_id") == team_id for t in teams)
    except Exception:
        logger.exception("Team membership check failed — denying access")
        return False


def with_identity(f):
    """Decorator that resolves ``Identity`` from the incoming request.

    Reads ``userId``, ``identityType`` (default ``"user"``), and
    ``displayName`` from query parameters **or** JSON body and passes the
    resulting ``Identity`` as the ``identity`` keyword argument.

    Returns **400** when ``userId`` is absent or ``identityType`` is
    unrecognised, so the endpoint never has to handle those error cases.

    Usage::

        @bp.route("/things.list", methods=["GET"])
        @with_identity
        def list_things(identity):
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        body = request.get_json(silent=True) or {}

        user_id = request.args.get("userId") or body.get("userId")
        identity_type = (
            request.args.get("identityType")
            or body.get("identityType")
            or "user"
        )
        display_name = (
            request.args.get("displayName")
            or body.get("displayName")
            or ""
        )

        if not user_id:
            return jsonify({"error": "userId is required"}), 400

        try:
            kwargs["identity"] = resolve_identity(
                user_id, identity_type, display_name,
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        return f(*args, **kwargs)
    return decorated

