"""
Flask decorators for identity resolution and authorization.

MAS owns its own auth decorators. They validate the caller via a Redis-backed
server session (set by the Identity service at login) and delegate
team-membership logic through the IdentityProvider port.

UI and CLI authenticate via the Flask session cookie.
Headless scripts/CI may fall back to the ``X-Authenticated-User`` header
until API-token support is implemented (see design-genie-1618.md §7).

The header fallback is injected via the ``get_fallback_user`` callback on
``require_team_session`` from ``global_utils`` — one removal point when
API tokens land.
"""
import logging
from functools import wraps
from typing import Optional, Tuple

from flask import current_app, g, jsonify, request, session

from global_utils.flask.decorators import (
    G_USER_ID,
    require_team_session,
)
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
# Session callbacks (plugged into global_utils decorators)
# ──────────────────────────────────────────────────────────────────────────────

_AUTH_HEADER = "X-Authenticated-User"


def _get_fallback_user() -> str | None:
    """Legacy fallback: read ``X-Authenticated-User`` header.

    Used by headless CI/CD scripts that cannot perform browser SSO
    (e.g. ``scripts/execution_workflow.py``).  Will be removed when
    API-token auth is implemented (design §7).
    """
    user = request.headers.get(_AUTH_HEADER, "").strip()
    if user:
        logger.debug("Authenticated via %s header (legacy): %s", _AUTH_HEADER, user)
    return user or None


def _get_team_id() -> str | None:
    """Return the team id from the request when identityType is ``team``."""
    body = request.get_json(silent=True) or {}
    identity_type = (
        request.args.get("identityType")
        or body.get("identityType")
        or "user"
    ).strip().lower()
    if identity_type == "team":
        return (request.args.get("userId") or body.get("userId") or "").strip() or None
    return None


def _check_team_membership(username: str, team_id: str) -> bool:
    return _identity_provider().is_member(username, team_id)


# Pre-built decorators — see design-genie-1618.md §3.7c
_mas_session = require_team_session(
    get_redis_store=_get_redis_store,
    get_session_id=lambda: session.get("session_id"),
    get_fallback_user=_get_fallback_user,
)

_mas_team_session = require_team_session(
    get_redis_store=_get_redis_store,
    get_session_id=lambda: session.get("session_id"),
    get_team_id=_get_team_id,
    team_membership_checker=_check_team_membership,
    get_fallback_user=_get_fallback_user,
)


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
    """Validate the caller's session and inject ``authenticated_user``.

    Delegates to ``require_team_session`` from ``global_utils`` (with the
    header-fallback callback).  After validation, ``g.user_id`` is bridged
    into the ``authenticated_user`` kwarg that endpoints expect.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        kwargs["authenticated_user"] = getattr(g, G_USER_ID, "")
        return f(*args, **kwargs)
    return _mas_session(decorated)


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
    """Validate caller session, authorize, and resolve ``Identity``.

    Delegates to ``require_team_session`` from ``global_utils`` (with
    header-fallback and team-membership callbacks).

    1. Session validation + team membership → handled by ``_mas_team_session``.
    2. **user** identity: ``userId`` must match ``g.user_id`` → 403.
    3. Resolves ``Identity`` and injects it as ``identity`` kwarg → 400 on invalid.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        authenticated_user = getattr(g, G_USER_ID, "")
        user_id, identity_type_raw, _ = _parse_identity_params(kwargs)

        if identity_type_raw != "team":
            if user_id and user_id.casefold() != authenticated_user.casefold():
                return jsonify({
                    "error": "Access denied: userId does not match authenticated user",
                    "error_type": "USER_ACCESS_DENIED",
                }), 403

        identity, err = _resolve_identity_or_error(kwargs)
        if err:
            return err
        kwargs["identity"] = identity
        return f(*args, **kwargs)

    return _mas_team_session(decorated)


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
