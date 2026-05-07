"""
Flask endpoints for the Collaboration Hub.

Enables multi-user participation in sessions:
- Join / leave / heartbeat for presence tracking
- Query participants in a session
- List active sessions for a team
- List sessions a specific user is participating in
"""
import logging

from flask import Blueprint, jsonify, current_app, request
from global_utils.helpers.apiargs import from_body, from_query
from inbound.flask.decorators import _is_team_member
from mas.collaboration.models import ParticipantRole
from webargs import fields

logger = logging.getLogger(__name__)

_EDIT_LOCK_KINDS = frozenset({"resource", "blueprint"})

collaboration_bp = Blueprint("collaboration", __name__)


def _collab_svc():
    svc = current_app.container.collaboration_service
    if svc is None:
        return None
    return svc


def _unavailable():
    return jsonify({
        "error": "Collaboration service not available — Redis is not configured"
    }), 501


def _invalid_edit_lock_kind():
    return jsonify({
        "error": f"entityKind must be one of: {', '.join(sorted(_EDIT_LOCK_KINDS))}"
    }), 400


def _validate_user(user_id: str):
    """Verify the claimed userId matches the authenticated caller.

    Returns an error tuple ``(response, status)`` when validation fails,
    or ``None`` when the caller is legitimate (or no auth header is present).
    """
    authenticated = request.headers.get("X-Authenticated-User", "").strip()
    if authenticated and authenticated != user_id:
        return jsonify({"error": "userId does not match authenticated user"}), 403
    return None


def _validate_team(team_id: str):
    """Verify authenticated caller is a member of the requested team."""
    authenticated = request.headers.get("X-Authenticated-User", "").strip()
    if authenticated and not _is_team_member(authenticated, team_id):
        return jsonify({"error": "Access denied: you are not a member of this team"}), 403
    return None


# ── Join / Leave / Heartbeat ────────────────────────────────────────

@collaboration_bp.route("/session.join", methods=["POST"])
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "user_id": fields.Str(data_key="userId", required=True),
    "display_name": fields.Str(data_key="displayName", load_default=""),
    "role": fields.Str(data_key="role", load_default="collaborator"),
})
def join_session(session_id, user_id, display_name, role):
    auth_err = _validate_user(user_id)
    if auth_err:
        return auth_err
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        participant_role = ParticipantRole(role)
        participants = svc.join_session(
            session_id=session_id,
            user_id=user_id,
            display_name=display_name,
            role=participant_role,
        )
        return jsonify(participants.model_dump(mode="json")), 200
    except KeyError:
        return jsonify({"error": f"Session {session_id} not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("join_session failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_bp.route("/session.leave", methods=["POST"])
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "user_id": fields.Str(data_key="userId", required=True),
})
def leave_session(session_id, user_id):
    auth_err = _validate_user(user_id)
    if auth_err:
        return auth_err
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        svc.leave_session(session_id=session_id, user_id=user_id)
        return jsonify({"success": True}), 200
    except Exception:
        logger.exception("leave_session failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_bp.route("/session.heartbeat", methods=["POST"])
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "user_id": fields.Str(data_key="userId", required=True),
})
def heartbeat(session_id, user_id):
    auth_err = _validate_user(user_id)
    if auth_err:
        return auth_err
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        svc.heartbeat(session_id=session_id, user_id=user_id)
        return jsonify({"success": True}), 200
    except Exception:
        logger.exception("heartbeat failed")
        return jsonify({"error": "Internal server error"}), 500


# ── Queries ─────────────────────────────────────────────────────────

@collaboration_bp.route("/session.participants", methods=["GET"])
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def get_participants(session_id):
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        participants = svc.get_participants(session_id)
        return jsonify(participants.model_dump(mode="json")), 200
    except Exception:
        logger.exception("get_participants failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_bp.route("/team.sessions", methods=["GET"])
@from_query({
    "team_id": fields.Str(data_key="teamId", required=True),
})
def get_team_sessions(team_id):
    team_err = _validate_team(team_id)
    if team_err:
        return team_err
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        index = svc.get_team_sessions(team_id)
        return jsonify(index.model_dump(mode="json")), 200
    except Exception:
        logger.exception("get_team_sessions failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_bp.route("/user.active_sessions", methods=["GET"])
@from_query({
    "user_id": fields.Str(data_key="userId", required=True),
})
def get_user_active_sessions(user_id):
    auth_err = _validate_user(user_id)
    if auth_err:
        return auth_err
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        session_ids = svc.get_user_active_sessions(user_id)
        return jsonify({"userId": user_id, "activeSessions": session_ids}), 200
    except Exception:
        logger.exception("get_user_active_sessions failed")
        return jsonify({"error": "Internal server error"}), 500


# ── Typing indicators ────────────────────────────────────────────

@collaboration_bp.route("/session.typing", methods=["POST"])
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "user_id": fields.Str(data_key="userId", required=True),
    "is_typing": fields.Bool(data_key="isTyping", load_default=True),
})
def set_typing(session_id, user_id, is_typing):
    auth_err = _validate_user(user_id)
    if auth_err:
        return auth_err
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        if is_typing:
            svc.set_typing(session_id=session_id, user_id=user_id)
        else:
            svc.clear_typing(session_id=session_id, user_id=user_id)
        return jsonify({"success": True}), 200
    except Exception:
        logger.exception("set_typing failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_bp.route("/session.typing", methods=["GET"])
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def get_typing(session_id):
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        users = svc.get_typing_users(session_id)
        return jsonify({"sessionId": session_id, "typingUsers": users}), 200
    except Exception:
        logger.exception("get_typing failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_bp.route("/health", methods=["GET"])
def collaboration_health():
    svc = _collab_svc()
    if svc is None:
        return jsonify({"available": False, "reason": "not_configured"}), 200
    return jsonify({"available": svc.is_available()}), 200


# ── Team workspace edit locks (resources / blueprints) ───────────────


def _holder_to_json(holder):
    if holder is None:
        return None
    return {
        "userId": holder.user_id,
        "displayName": holder.display_name or holder.user_id,
    }


@collaboration_bp.route("/edit_lock.acquire", methods=["POST"])
@from_body({
    "team_id": fields.Str(data_key="teamId", required=True),
    "entity_kind": fields.Str(data_key="entityKind", required=True),
    "entity_id": fields.Str(data_key="entityId", required=True),
    "user_id": fields.Str(data_key="userId", required=True),
    "display_name": fields.Str(data_key="displayName", load_default=""),
})
def edit_lock_acquire(team_id, entity_kind, entity_id, user_id, display_name):
    auth_err = _validate_user(user_id)
    if auth_err:
        return auth_err
    if entity_kind not in _EDIT_LOCK_KINDS:
        return _invalid_edit_lock_kind()
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        acquired, holder = svc.acquire_team_edit_lock(
            team_id=team_id,
            entity_kind=entity_kind,
            entity_id=entity_id,
            user_id=user_id,
            display_name=display_name,
        )
        body = {"acquired": acquired}
        if not acquired and holder is not None:
            body["lockedBy"] = _holder_to_json(holder)
        return jsonify(body), 200
    except Exception:
        logger.exception("edit_lock_acquire failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_bp.route("/edit_lock.release", methods=["POST"])
@from_body({
    "team_id": fields.Str(data_key="teamId", required=True),
    "entity_kind": fields.Str(data_key="entityKind", required=True),
    "entity_id": fields.Str(data_key="entityId", required=True),
    "user_id": fields.Str(data_key="userId", required=True),
})
def edit_lock_release(team_id, entity_kind, entity_id, user_id):
    auth_err = _validate_user(user_id)
    if auth_err:
        return auth_err
    if entity_kind not in _EDIT_LOCK_KINDS:
        return _invalid_edit_lock_kind()
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        svc.release_team_edit_lock(team_id, entity_kind, entity_id, user_id)
        return jsonify({"success": True}), 200
    except Exception:
        logger.exception("edit_lock_release failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_bp.route("/edit_lock.heartbeat", methods=["POST"])
@from_body({
    "team_id": fields.Str(data_key="teamId", required=True),
    "entity_kind": fields.Str(data_key="entityKind", required=True),
    "entity_id": fields.Str(data_key="entityId", required=True),
    "user_id": fields.Str(data_key="userId", required=True),
    "display_name": fields.Str(data_key="displayName", load_default=""),
})
def edit_lock_heartbeat(team_id, entity_kind, entity_id, user_id, display_name):
    auth_err = _validate_user(user_id)
    if auth_err:
        return auth_err
    if entity_kind not in _EDIT_LOCK_KINDS:
        return _invalid_edit_lock_kind()
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        renewed = svc.renew_team_edit_lock(
            team_id, entity_kind, entity_id, user_id, display_name
        )
        return jsonify({"renewed": renewed}), 200
    except Exception:
        logger.exception("edit_lock_heartbeat failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_bp.route("/edit_lock.status", methods=["GET"])
@from_query({
    "team_id": fields.Str(data_key="teamId", required=True),
    "entity_kind": fields.Str(data_key="entityKind", required=True),
    "entity_id": fields.Str(data_key="entityId", required=True),
})
def edit_lock_status(team_id, entity_kind, entity_id):
    if entity_kind not in _EDIT_LOCK_KINDS:
        return _invalid_edit_lock_kind()
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        holder = svc.get_team_edit_lock(team_id, entity_kind, entity_id)
        return jsonify({"locked": holder is not None, "lockedBy": _holder_to_json(holder)}), 200
    except Exception:
        logger.exception("edit_lock_status failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_bp.route("/edit_lock.statuses", methods=["POST"])
@from_body({
    "team_id": fields.Str(data_key="teamId", required=True),
    "entity_kind": fields.Str(data_key="entityKind", required=True),
    "entity_ids": fields.List(fields.Str(), data_key="entityIds", required=True),
})
def edit_lock_statuses(team_id, entity_kind, entity_ids):
    if entity_kind not in _EDIT_LOCK_KINDS:
        return _invalid_edit_lock_kind()
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        batch = svc.get_team_edit_locks_batch(team_id, entity_kind, entity_ids)
        locks = {
            eid: _holder_to_json(h) if h is not None else None
            for eid, h in batch.items()
        }
        return jsonify({"locks": locks}), 200
    except Exception:
        logger.exception("edit_lock_statuses failed")
        return jsonify({"error": "Internal server error"}), 500
