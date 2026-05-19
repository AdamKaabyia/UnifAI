import logging
from typing import Optional, Tuple

from flask import current_app, jsonify, request

from mas.collaboration.service import CollaborationService
from mas.core.identity import IdentityType

logger = logging.getLogger(__name__)

EDIT_LOCK_KINDS = frozenset({"resource", "blueprint"})


def _acting_user_id() -> str | None:
    return request.headers.get("X-Authenticated-User", "").strip() or None


def collab_service():
    return current_app.container.collaboration_service


def unavailable():
    return jsonify(
        {"error": "Collaboration service not available - Redis is not configured"}
    ), 501


def invalid_edit_lock_kind():
    return jsonify(
        {"error": f"entityKind must be one of: {', '.join(sorted(EDIT_LOCK_KINDS))}"}
    ), 400


def internal_error(log: logging.Logger, action: str):
    log.exception("%s failed", action)
    return jsonify({"error": "Internal server error"}), 500


def validate_user(user_id: str):
    """Verify the claimed userId matches the authenticated caller."""
    authenticated = request.headers.get("X-Authenticated-User", "").strip()
    if not authenticated:
        return jsonify({"error": "Missing authenticated user"}), 401
    if authenticated.casefold() != (user_id or "").casefold():
        return jsonify({"error": "userId does not match authenticated user"}), 403
    return None


def validate_team(team_id: str):
    """Verify authenticated caller is a member of the requested team."""
    authenticated = request.headers.get("X-Authenticated-User", "").strip()
    if not authenticated:
        return jsonify({"error": "Missing authenticated user"}), 401
    if not current_app.container.identity_teams_client.is_member(authenticated, team_id):
        return jsonify({"error": "Access denied: you are not a member of this team"}), 403
    return None


def validate_session_access(session_id: str):
    """Require auth header and Mongo session ownership (user or team member)."""
    authenticated = request.headers.get("X-Authenticated-User", "").strip()
    if not authenticated:
        return None, (jsonify({"error": "Missing authenticated user"}), 401)
    repo = current_app.container.session_repo
    try:
        record = repo.fetch(session_id)
    except KeyError:
        return None, (jsonify({"error": f"Session {session_id} not found"}), 404)
    if record.identity.type == IdentityType.TEAM:
        if not current_app.container.identity_teams_client.is_member(authenticated, record.identity.id):
            return None, (jsonify({"error": "Access denied"}), 403)
    elif authenticated.casefold() != record.identity.id.casefold():
        return None, (jsonify({"error": "Access denied"}), 403)
    return record, None


def validate_edit_lock_kind(entity_kind: str):
    if entity_kind not in EDIT_LOCK_KINDS:
        return invalid_edit_lock_kind()
    return None


def service_or_unavailable() -> Tuple[Optional[CollaborationService], Optional[tuple]]:
    svc = collab_service()
    if svc is None:
        return None, unavailable()
    return svc, None


def service_for_user(user_id: str) -> Tuple[Optional[CollaborationService], Optional[tuple]]:
    auth_err = validate_user(user_id)
    if auth_err:
        return None, auth_err
    return service_or_unavailable()


def service_for_team(team_id: str) -> Tuple[Optional[CollaborationService], Optional[tuple]]:
    team_err = validate_team(team_id)
    if team_err:
        return None, team_err
    return service_or_unavailable()


def service_for_user_team(user_id: str, team_id: str) -> Tuple[Optional[CollaborationService], Optional[tuple]]:
    auth_err = validate_user(user_id)
    if auth_err:
        return None, auth_err
    return service_for_team(team_id)


def holder_to_json(holder):
    if holder is None:
        return None
    return {
        "userId": holder.user_id,
        "displayName": holder.display_name or holder.user_id,
    }
