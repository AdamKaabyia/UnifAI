"""
Decorators for Flask endpoints.
"""
import logging
import time
from functools import wraps
from threading import Lock

from flask import jsonify, request, current_app

import requests as http_requests

from inbound.flask.identity_helpers import resolve_identity

logger = logging.getLogger(__name__)

# Cache Identity ``teams.list`` results per user to avoid one HTTP call per
# decorated request. TTL is short so membership revocations take effect quickly.
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


def _fetch_team_ids_from_identity(username: str, base: str) -> frozenset[str]:
    resp = http_requests.get(
        f"{base}/api/teams/teams.list",
        params={"userId": username},
        timeout=5,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"teams.list HTTP {resp.status_code}")
    teams = resp.json().get("teams", [])
    return frozenset(
        str(t.get("team_id"))
        for t in teams
        if t.get("team_id") is not None
    )


def _identity_service_base() -> str:
    """Base URL for the Identity pod (teams + directory HTTP APIs).

    ``directory_sso_url`` is the legacy name; ``identity_host`` from main is
    preferred when the former is unset.
    """
    return (
        (current_app.config.get("directory_sso_url") or "")
        or (current_app.config.get("identity_host") or "")
    ).rstrip("/")


def _require_auth_header_enforced() -> bool:
    """Whether ``X-Authenticated-User`` must be present for guarded decorators."""
    if current_app.config.get("require_auth_header"):
        return True
    return bool(_identity_service_base())


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

    Reads ``X-Authenticated-User`` from the request header (set by the UI /
    ingress from the SSO session). For **user** identity: the claimed
    ``userId`` must match the header. For **team** identity: the authenticated
    user must be a member of the claimed team (verified via the Identity pod
    ``/api/teams/teams.list``, with a short in-process cache per user).

    When ``_require_auth_header_enforced()`` is true (Identity base URL is
    configured and/or ``REQUIRE_AUTH_HEADER`` / ``require_auth_header`` is set),
    requests without ``X-Authenticated-User`` receive **401**.

    Otherwise the header is optional (direct/internal calls); when present,
    claimed user/team identity is still validated below.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        authenticated_user = request.headers.get("X-Authenticated-User", "").strip()
        if not authenticated_user:
            if _require_auth_header_enforced():
                return jsonify({
                    "error": "Missing authenticated user",
                    "error_type": "AUTHENTICATION_REQUIRED",
                }), 401
            return f(*args, **kwargs)

        body = request.get_json(silent=True) or {}
        identity_type = (
            kwargs.get("identity_type")
            or request.args.get("identityType")
            or body.get("identityType")
            or "user"
        )
        identity_type = str(identity_type).strip().lower() or "user"

        claimed_id = (
            kwargs.get("user_id")
            or kwargs.get("userId")
            or request.args.get("userId")
            or body.get("userId")
            or ""
        )
        claimed_id = str(claimed_id).strip()

        if identity_type == "team":
            if not claimed_id:
                return f(*args, **kwargs)
            if not _is_team_member(authenticated_user, claimed_id):
                return jsonify({
                    "error": "Access denied: you are not a member of this team",
                    "error_type": "TEAM_ACCESS_DENIED",
                }), 403
            return f(*args, **kwargs)

        if claimed_id and claimed_id.casefold() != authenticated_user.casefold():
            return jsonify({
                "error": "Access denied: userId does not match authenticated user",
                "error_type": "USER_ACCESS_DENIED",
            }), 403

        return f(*args, **kwargs)

    return decorated_function


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
