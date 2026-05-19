"""
Flask decorators for access control.

Pluggable so each app can supply its own way to get the current user
and to check admin status (e.g. from config, DB, or admin config service).

Also provides identity-pod-backed decorators that validate callers against
the Identity service and inject resolved Identity objects into endpoint
handlers. These are designed to be consumed by any Flask-based service
(MAS, RAG, etc.) without duplication.
"""
import logging
import time
from functools import wraps
from threading import Lock
from typing import Any, Callable

import requests as http_requests
from flask import current_app, g, jsonify, request, session

from global_utils.identity import Identity, IdentityType, resolve_identity
from global_utils.redis import get_identity_session, get_identity_username

logger = logging.getLogger(__name__)

# g attribute names (single place for both helpers as all modules will use the same functions)
G_IDENTITY_SESSION = "identity_session"
G_IDENTITY_USERNAME = "identity_username"

# ──────────────────────────────────────────────────────────────────────────────
# Pluggable identity base URL provider
#
# Services that own an outbound IdentityTeamsClient should call
# ``configure_identity_base(url)`` at startup instead of populating Flask's
# ``app.config["identity_host"]`` / ``app.config["directory_sso_url"]``.
# When configured this way, the decorators never read identity-related values
# from Flask's app config, keeping the inbound adapter free of identity logic.
# ──────────────────────────────────────────────────────────────────────────────

_configured_identity_base: str = ""


def configure_identity_base(base_url: str) -> None:
    """Register the Identity pod base URL for use by auth decorators.

    Call this once at app startup (e.g. from the Flask app factory) with the
    resolved identity host URL.  When set, ``_identity_service_base()`` uses
    this value instead of reading from Flask's ``app.config``.
    """
    global _configured_identity_base
    _configured_identity_base = (base_url or "").rstrip("/")


# ──────────────────────────────────────────────────────────────────────────────
# Team-membership cache – short TTL so revocations take effect quickly
# ──────────────────────────────────────────────────────────────────────────────

_TEAM_IDS_CACHE_TTL_SEC = 45.0
_team_ids_cache: dict[str, tuple[float, frozenset[str]]] = {}
_team_ids_cache_lock = Lock()


def _get_cached_team_ids(username: str) -> frozenset[str] | None:
    now = time.monotonic()
    with _team_ids_cache_lock:
        entry = _team_ids_cache.get(username)
        if entry is not None and (now - entry[0]) < _TEAM_IDS_CACHE_TTL_SEC:
            return entry[1]
    return None


def _set_cached_team_ids(username: str, team_ids: frozenset[str]) -> None:
    with _team_ids_cache_lock:
        _team_ids_cache[username] = (time.monotonic(), team_ids)


def _fetch_teams_payload_from_identity(username: str, base: str) -> list:
    """Raw ``teams`` array from Identity ``teams.list`` for *username*."""
    resp = http_requests.get(
        f"{base}/api/teams/teams.list",
        params={"userId": username},
        timeout=5,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"teams.list HTTP {resp.status_code}")
    return resp.json().get("teams", []) or []


def _fetch_team_ids_from_identity(username: str, base: str) -> frozenset[str]:
    teams = _fetch_teams_payload_from_identity(username, base)
    return frozenset(
        str(t.get("team_id"))
        for t in teams
        if t.get("team_id") is not None
    )


def _resolve_team_id_for_member(username: str, team_name_or_id: str) -> str | None:
    """Map a team display name or ``team_id`` to the canonical id for teams the user may access.

    Used by APIs that accept a human-readable ``teamName`` while membership checks
    and workspace ownership use ``team_id``.

    When no Identity base URL is configured, returns *team_name_or_id* stripped
    (legacy / local dev — no server-side validation).

    Returns ``None`` when Identity is configured but the user has no matching team
    or ``teams.list`` fails.
    """
    raw = str(team_name_or_id).strip()
    if not raw:
        return None

    base = _identity_service_base()
    if not base:
        return raw

    try:
        teams = _fetch_teams_payload_from_identity(username, base)
    except Exception:
        logger.exception("teams.list failed during team id resolution")
        return None

    for t in teams:
        tid = str(t.get("team_id") or "").strip()
        if not tid:
            continue
        if raw.casefold() == tid.casefold():
            return tid
        nm = str(t.get("name") or "").strip()
        if nm and raw.casefold() == nm.casefold():
            return tid
    return None


def _identity_service_base() -> str:
    """Base URL for the Identity pod (teams + directory HTTP APIs).

    Prefers the value registered via :func:`configure_identity_base`.
    Falls back to Flask ``app.config`` (legacy — for services that have not
    yet migrated to the outbound IdentityTeamsClient pattern).
    """
    if _configured_identity_base:
        return _configured_identity_base
    return (
        (current_app.config.get("directory_sso_url") or "")
        or (current_app.config.get("identity_host") or "")
    ).rstrip("/")


def _require_auth_header_enforced() -> bool:
    """Whether ``X-Authenticated-User`` must be present for guarded decorators."""
    if current_app.config.get("require_auth_header"):
        return True
    return bool(_identity_service_base())


def _is_team_member(username: str, team_id: str) -> bool:
    """Check team membership via the Identity pod ``teams.list`` endpoint.

    Fails **closed** (denies access) when the Identity base URL is configured but
    the service is unreachable or returns an error. Skips the check when no
    base URL is set (e.g. local dev without Identity).

    Successful ``teams.list`` responses are cached briefly per username to
    reduce load on Identity (see ``_TEAM_IDS_CACHE_TTL_SEC``).
    """
    base = _identity_service_base()
    if not base:
        return True

    cached = _get_cached_team_ids(username)
    if cached is not None:
        return team_id in cached

    try:
        team_ids = _fetch_team_ids_from_identity(username, base)
        _set_cached_team_ids(username, team_ids)
        return team_id in team_ids
    except Exception:
        logger.exception("Team membership check failed — denying access")
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Pluggable decorators (each app supplies its own user/admin resolvers)
# ──────────────────────────────────────────────────────────────────────────────

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


def require_identity_session(
    get_redis_store: Callable[[], Any],
    get_session_id: Callable[[], str | None] | None = None,
) -> Callable:
    """
    Decorator factory: require a valid identity server session in Redis.
    A session is "valid" when :class:`UserSessionData.has_auth_credentials` is true
    (same idea as the identity service ``is_authenticated`` w.r.t. username + access_token).
    Each app supplies:
      - get_redis_store() -> store with ``hget`` (e.g. :class:`global_utils.redis.RedisKVStore`)
      - get_session_id() -> str | None (optional; default: ``session.get("session_id")``)
    On success: sets ``g.identity_session`` to a :class:`UserSessionData` (see
    :data:`G_IDENTITY_SESSION` for the string key if you use ``getattr``/``setattr``).
    On failure: 401 with JSON; unexpected errors: 500 with error_type.
    """
    get_sid = get_session_id or (lambda: session.get("session_id"))
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                data = get_identity_session(get_redis_store(), get_sid())
                if data is None or not data.has_auth_credentials():
                    return (
                        jsonify(
                            {
                                "error": "Not authenticated",
                                "error_type": "AUTHENTICATION_REQUIRED",
                            }
                        ),
                        401,
                    )
                setattr(g, G_IDENTITY_SESSION, data)
                return f(*args, **kwargs)
            except Exception as e:
                return (
                    jsonify(
                        {
                            "error": f"Access control error: {e!s}",
                            "error_type": "ACCESS_CONTROL_ERROR",
                        }
                    ),
                    500,
                )
        return wrapped
    return decorator


def require_identity_username(
    get_redis_store: Callable[[], Any],
    get_session_id: Callable[[], str | None] | None = None,
) -> Callable:
    """
    Decorator factory: require a non-empty ``username`` from the Redis server session.
    Weaker than :func:`require_identity_session` (does not check access_token).
    Prefer the full session decorator for API paths that need the same bar as identity.
    On success: sets ``g.identity_username`` (see :data:`G_IDENTITY_USERNAME`).
    """
    get_sid = get_session_id or (lambda: session.get("session_id"))
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                username = get_identity_username(get_redis_store(), get_sid())
                if not username:
                    return (
                        jsonify(
                            {
                                "error": "Not authenticated",
                                "error_type": "AUTHENTICATION_REQUIRED",
                            }
                        ),
                        401,
                    )
                setattr(g, G_IDENTITY_USERNAME, username)
                return f(*args, **kwargs)
            except Exception as e:
                return (
                    jsonify(
                        {
                            "error": f"Access control error: {e!s}",
                            "error_type": "ACCESS_CONTROL_ERROR",
                        }
                    ),
                    500,
                )
        return wrapped
    return decorator


# ──────────────────────────────────────────────────────────────────────────────
# Identity-pod-backed request decorators
# ──────────────────────────────────────────────────────────────────────────────

def with_authenticated_user(f):
    """Decorator that extracts and validates the ``X-Authenticated-User`` header.

    Reads ``X-Authenticated-User`` from the request header and injects it as
    the ``authenticated_user`` keyword argument.

    When ``_require_auth_header_enforced()`` is true (Identity URL configured
    or ``REQUIRE_AUTH_HEADER`` set), requests without the header receive **401**.
    In permissive mode (local dev / no Identity URL) the header is optional and
    an empty string is injected when absent.

    Usage::

        @bp.route("/things.create", methods=["POST"])
        @with_authenticated_user
        @from_body({...})
        def create_thing(authenticated_user, ...):
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        authenticated_user = request.headers.get("X-Authenticated-User", "").strip()
        if not authenticated_user and _require_auth_header_enforced():
            return jsonify({
                "error": "Missing authenticated user",
                "error_type": "AUTHENTICATION_REQUIRED",
            }), 401
        kwargs["authenticated_user"] = authenticated_user
        return f(*args, **kwargs)
    return decorated


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
            kwargs["identity"] = resolve_identity(user_id, identity_type, display_name)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        return f(*args, **kwargs)
    return decorated


def with_require_identity_authorization(f):
    """Validate caller authorization **and** resolve ``Identity`` in one step.

    Combines an authorization check (via the Identity pod ``teams.list``) with
    identity resolution so endpoints only need a single decorator.

    Execution order:

    1. Reads ``X-Authenticated-User`` from the request header.
       - If the header is required (Identity URL configured or
         ``REQUIRE_AUTH_HEADER`` set) and missing → **401**.
       - If present, validates the claimed identity:
         - **user** identity: ``userId`` must match the header value → **403**
           on mismatch.
         - **team** identity: the authenticated user must be a member of the
           claimed team (via Identity ``teams.list``) → **403** if not.
    2. Resolves ``Identity`` from ``userId`` / ``identityType`` /
       ``displayName`` (query params or JSON body) and injects it as the
       ``identity`` keyword argument → **400** when ``userId`` is absent or
       ``identityType`` is unrecognised.

    Usage::

        @bp.route("/things.list", methods=["GET"])
        @with_require_identity_authorization
        def list_things(identity):
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        body = request.get_json(silent=True) or {}

        # ── Authorization check ───────────────────────────────────────
        authenticated_user = request.headers.get("X-Authenticated-User", "").strip()
        if not authenticated_user:
            if _require_auth_header_enforced():
                return jsonify({
                    "error": "Missing authenticated user",
                    "error_type": "AUTHENTICATION_REQUIRED",
                }), 401
        else:
            identity_type_raw = str(
                kwargs.get("identity_type")
                or request.args.get("identityType")
                or body.get("identityType")
                or "user"
            ).strip().lower() or "user"

            claimed_id = str(
                kwargs.get("user_id")
                or kwargs.get("userId")
                or request.args.get("userId")
                or body.get("userId")
                or ""
            ).strip()

            if identity_type_raw == "team":
                if claimed_id and not _is_team_member(authenticated_user, claimed_id):
                    return jsonify({
                        "error": "Access denied: you are not a member of this team",
                        "error_type": "TEAM_ACCESS_DENIED",
                    }), 403
            elif claimed_id and claimed_id.casefold() != authenticated_user.casefold():
                return jsonify({
                    "error": "Access denied: userId does not match authenticated user",
                    "error_type": "USER_ACCESS_DENIED",
                }), 403

        # ── Identity resolution ───────────────────────────────────────
        user_id = request.args.get("userId") or body.get("userId")
        identity_type = (
            request.args.get("identityType")
            or body.get("identityType")
            or "user"
        )
        display_name = request.args.get("displayName") or body.get("displayName") or ""

        if not user_id:
            return jsonify({"error": "userId is required"}), 400

        try:
            kwargs["identity"] = resolve_identity(user_id, identity_type, display_name)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        return f(*args, **kwargs)

    return decorated
