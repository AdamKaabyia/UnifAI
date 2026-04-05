"""
Flask endpoints for the Collaboration Hub.

Enables multi-user participation in sessions:
- Join / leave / heartbeat for presence tracking
- Query participants in a session
- List active sessions for a team
- List sessions a specific user is participating in
"""
from flask import Blueprint, jsonify, current_app
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields

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


# ── Join / Leave / Heartbeat ────────────────────────────────────────

@collaboration_bp.route("/session.join", methods=["POST"])
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "user_id": fields.Str(data_key="userId", required=True),
    "display_name": fields.Str(data_key="displayName", load_default=""),
    "role": fields.Str(data_key="role", load_default="collaborator"),
})
def join_session(session_id, user_id, display_name, role):
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        from mas.collaboration.models import ParticipantRole
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@collaboration_bp.route("/session.leave", methods=["POST"])
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "user_id": fields.Str(data_key="userId", required=True),
})
def leave_session(session_id, user_id):
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        svc.leave_session(session_id=session_id, user_id=user_id)
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@collaboration_bp.route("/session.heartbeat", methods=["POST"])
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "user_id": fields.Str(data_key="userId", required=True),
})
def heartbeat(session_id, user_id):
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        svc.heartbeat(session_id=session_id, user_id=user_id)
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@collaboration_bp.route("/team.sessions", methods=["GET"])
@from_query({
    "team_id": fields.Str(data_key="teamId", required=True),
})
def get_team_sessions(team_id):
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        index = svc.get_team_sessions(team_id)
        return jsonify(index.model_dump(mode="json")), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@collaboration_bp.route("/user.active_sessions", methods=["GET"])
@from_query({
    "user_id": fields.Str(data_key="userId", required=True),
})
def get_user_active_sessions(user_id):
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        session_ids = svc.get_user_active_sessions(user_id)
        return jsonify({"userId": user_id, "activeSessions": session_ids}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Typing indicators ────────────────────────────────────────────

@collaboration_bp.route("/session.typing", methods=["POST"])
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "user_id": fields.Str(data_key="userId", required=True),
    "is_typing": fields.Bool(data_key="isTyping", load_default=True),
})
def set_typing(session_id, user_id, is_typing):
    svc = _collab_svc()
    if svc is None:
        return _unavailable()
    try:
        if is_typing:
            svc.set_typing(session_id=session_id, user_id=user_id)
        else:
            svc.clear_typing(session_id=session_id, user_id=user_id)
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@collaboration_bp.route("/health", methods=["GET"])
def collaboration_health():
    svc = _collab_svc()
    if svc is None:
        return jsonify({"available": False, "reason": "not_configured"}), 200
    return jsonify({"available": svc.is_available()}), 200
