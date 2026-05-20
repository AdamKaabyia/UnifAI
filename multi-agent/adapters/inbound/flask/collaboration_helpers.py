"""
Collaboration helper utilities for Flask endpoints.

Auth/identity is handled by the standard decorators (@with_authenticated_user).
These helpers provide collaboration-specific concerns: service availability,
session ownership validation, and edit-lock kind validation.
"""
import logging
from typing import Optional, Tuple

from flask import current_app, jsonify

from mas.collaboration.service import CollaborationService
from mas.core.identity import IdentityType

logger = logging.getLogger(__name__)

EDIT_LOCK_KINDS = frozenset({"resource", "blueprint"})


def collab_service() -> Optional[CollaborationService]:
    return current_app.container.collaboration_service


def service_or_unavailable() -> Tuple[Optional[CollaborationService], Optional[tuple]]:
    """Return the collaboration service, or a 501 error if Redis is not configured."""
    svc = collab_service()
    if svc is None:
        return None, (jsonify(
            {"error": "Collaboration service not available - Redis is not configured"}
        ), 501)
    return svc, None


def validate_session_access(authenticated_user: str, session_id: str):
    """Verify the authenticated user owns (or is a team member of) the session.

    Returns (session_record, None) on success, or (None, error_response) on failure.
    """
    repo = current_app.container.session_repo
    try:
        record = repo.fetch(session_id)
    except KeyError:
        return None, (jsonify({"error": f"Session {session_id} not found"}), 404)

    if record.identity.type == IdentityType.TEAM:
        provider = current_app.container.identity_provider
        if not provider.is_member(authenticated_user, record.identity.id):
            return None, (jsonify({"error": "Access denied"}), 403)
    elif authenticated_user.casefold() != record.identity.id.casefold():
        return None, (jsonify({"error": "Access denied"}), 403)

    return record, None


def validate_team_membership(authenticated_user: str, team_id: str) -> Optional[tuple]:
    """Verify the authenticated user is a member of the team.

    Returns None on success, or an error response tuple on failure.
    """
    provider = current_app.container.identity_provider
    if not provider.is_member(authenticated_user, team_id):
        return jsonify({"error": "Access denied: you are not a member of this team"}), 403
    return None


def validate_edit_lock_kind(entity_kind: str) -> Optional[tuple]:
    """Validate that entity_kind is a supported lock type."""
    if entity_kind not in EDIT_LOCK_KINDS:
        return jsonify(
            {"error": f"entityKind must be one of: {', '.join(sorted(EDIT_LOCK_KINDS))}"}
        ), 400
    return None


def internal_error(log: logging.Logger, action: str):
    log.exception("%s failed", action)
    return jsonify({"error": "Internal server error"}), 500


def holder_to_json(holder):
    if holder is None:
        return None
    return {
        "userId": holder.user_id,
        "displayName": holder.display_name or holder.user_id,
    }
