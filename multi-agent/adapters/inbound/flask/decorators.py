"""
Flask decorators for identity resolution and authorization.

MAS owns its own auth decorators. They validate the caller via a Redis-backed
server session (set by the Identity service at login) and delegate
team-membership logic through the IdentityProvider port.

UI and CLI authenticate via the Flask session cookie.
Headless scripts/CI may fall back to the ``X-Authenticated-User`` header
until API-token support is implemented.
"""
import logging
from functools import wraps
from typing import Optional, Tuple

from flask import current_app, g, jsonify, request, session

from global_utils.flask.decorators import _validate_session
from mas.core.identity import Identity, IdentityType, resolve_identity
from mas.core.identity.ports import IdentityProvider

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Provider access
# ──────────────────────────────────────────────────────────────────────────────

def _identity_provider() -> IdentityProvider:
    """Single access point for the identity provider.

    The provider is wired at startup in the container and attached to the app.
    """
    return current_app.container.identity_provider


def _get_redis_store():
    return current_app.container.redis_kv_store


# ──────────────────────────────────────────────────────────────────────────────
# Session-based authentication
# ──────────────────────────────────────────────────────────────────────────────

_AUTH_HEADER = "X-Authenticated-User"


def _resolve_authenticated_user() -> Tuple[Optional[str], Optional[tuple]]:
    """Resolve the authenticated username.

    Tries the Redis session cookie first.  Falls back to the legacy
    ``X-Authenticated-User`` header for headless scripts/CI that cannot
    perform browser SSO.  The header fallback will be removed once
    API-token support is available.

    Returns ``(username, None)`` on success or ``(None, error_response)``
    on failure.
    """
    get_sid = lambda: session.get("session_id")
    data, err = _validate_session(_get_redis_store, get_sid)

    if data is not None and data.username:
        g.identity_session = data
        return data.username, None

    # Fallback: legacy header for headless scripts/CI
    header_user = request.headers.get(_AUTH_HEADER, "").strip()
    if header_user:
        logger.debug("Authenticated via %s header (legacy): %s", _AUTH_HEADER, header_user)
        return header_user, None

    if err:
        msg, err_type, status = err
        return None, (jsonify({"error": msg, "error_type": err_type}), status)

    return None, (jsonify({
        "error": "Not authenticated",
        "error_type": "AUTHENTICATION_REQUIRED",
    }), 401)


# ──────────────────────────────────────────────────────────────────────────────
# Request parameter extraction
# ──────────────────────────────────────────────────────────────────────────────

def _parse_identity_params(kwargs: dict) -> Tuple[str, str, str]:
    """Extract ``(user_id, identity_type, display_name)`` from the request.

    Reads from query parameters first, then JSON body, then *kwargs*
    (injected by ``@from_body`` / ``@from_query``).
    """
    body = request.get_json(silent=True) or {}
    user_id = (
        request.args.get("userId")
        or body.get("userId")
        or kwargs.get("userId")
        or kwargs.get("user_id")
        or ""
    )
    identity_type = (
        request.args.get("identityType")
        or body.get("identityType")
        or kwargs.get("identityType")
        or kwargs.get("identity_type")
        or "user"
    )
    display_name = (
        request.args.get("displayName")
        or body.get("displayName")
        or kwargs.get("displayName")
        or kwargs.get("display_name")
        or ""
    )
    return str(user_id).strip(), str(identity_type).strip().lower() or "user", str(display_name)


def _resolve_identity_or_error(kwargs: dict) -> Tuple[Optional[Identity], Optional[tuple]]:
    """Parse identity params and resolve, returning ``(identity, None)`` or ``(None, error_response)``."""
    user_id, identity_type, display_name = _parse_identity_params(kwargs)
    if not user_id:
        return None, (jsonify({"error": "userId is required"}), 400)
    try:
        return resolve_identity(user_id, identity_type, display_name), None
    except ValueError as e:
        return None, (jsonify({"error": str(e)}), 400)


# ──────────────────────────────────────────────────────────────────────────────
# Decorators
# ──────────────────────────────────────────────────────────────────────────────

def with_authenticated_user(f):
    """Validate the caller's Redis session and inject ``authenticated_user``.

    Validates the Flask session cookie against the Redis server session.
    Returns 401 if no valid session is found.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        authenticated_user, err = _resolve_authenticated_user()
        if err:
            return err
        kwargs["authenticated_user"] = authenticated_user
        return f(*args, **kwargs)
    return decorated


def with_identity(f):
    """Resolve ``Identity`` from the incoming request.

    Reads ``userId``, ``identityType``, and ``displayName`` from query
    parameters or JSON body and passes the resulting ``Identity`` as
    the ``identity`` keyword argument. Returns 400 on invalid input.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        identity, err = _resolve_identity_or_error(kwargs)
        if err:
            return err
        kwargs["identity"] = identity
        return f(*args, **kwargs)
    return decorated


def with_require_identity_authorization(f):
    """Validate caller session AND authorize + resolve ``Identity`` in one step.

    1. Validates the Redis session → 401 if invalid/expired.
    2. Validates the claimed identity:
       - **user** identity: ``userId`` must match the authenticated user → 403.
       - **team** identity: the authenticated user must be a member → 403.
    3. Resolves ``Identity`` and injects it as ``identity`` kwarg → 400 on invalid.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        provider = _identity_provider()
        user_id, identity_type_raw, _ = _parse_identity_params(kwargs)

        # ── Authentication ────────────────────────────────────────────
        authenticated_user, err = _resolve_authenticated_user()
        if err:
            return err

        # ── Authorization ─────────────────────────────────────────────
        if identity_type_raw == "team":
            if user_id and not provider.is_member(authenticated_user, user_id):
                return jsonify({
                    "error": "Access denied: you are not a member of this team",
                    "error_type": "TEAM_ACCESS_DENIED",
                }), 403
        elif user_id and user_id.casefold() != authenticated_user.casefold():
            return jsonify({
                "error": "Access denied: userId does not match authenticated user",
                "error_type": "USER_ACCESS_DENIED",
            }), 403

        # ── Identity resolution ───────────────────────────────────────
        identity, err = _resolve_identity_or_error(kwargs)
        if err:
            return err
        kwargs["identity"] = identity
        return f(*args, **kwargs)

    return decorated


def require_admin_access(f):
    """Gate an endpoint to users listed in ``admin_allowed_users``.

    Reads ``userId`` from kwargs (injected by ``@from_query``) or from the
    ``userId`` / ``user_id`` query parameter.
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
