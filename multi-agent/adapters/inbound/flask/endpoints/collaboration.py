"""
Flask collaboration presence and typing endpoints.
"""
import logging

from flask import Blueprint, jsonify
from global_utils.helpers.apiargs import from_body, from_query
from mas.collaboration.models import ParticipantRole
from webargs import fields

from inbound.flask.endpoints.collaboration_common import (
    internal_error,
    service_for_team,
    service_for_user,
    service_or_unavailable,
)

logger = logging.getLogger(__name__)

collaboration_bp = Blueprint("collaboration", __name__)


# ── Join / Leave / Heartbeat ────────────────────────────────────────

@collaboration_bp.route("/session.join", methods=["POST"])
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "user_id": fields.Str(data_key="userId", required=True),
    "display_name": fields.Str(data_key="displayName", load_default=""),
    "role": fields.Str(data_key="role", load_default="collaborator"),
})
def join_session(session_id, user_id, display_name, role):
    svc, err = service_for_user(user_id)
    if err:
        return err
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
        return internal_error(logger, "join_session")


@collaboration_bp.route("/session.leave", methods=["POST"])
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "user_id": fields.Str(data_key="userId", required=True),
})
def leave_session(session_id, user_id):
    svc, err = service_for_user(user_id)
    if err:
        return err
    try:
        svc.leave_session(session_id=session_id, user_id=user_id)
        return jsonify({"success": True}), 200
    except Exception:
        return internal_error(logger, "leave_session")


@collaboration_bp.route("/session.heartbeat", methods=["POST"])
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "user_id": fields.Str(data_key="userId", required=True),
})
def heartbeat(session_id, user_id):
    svc, err = service_for_user(user_id)
    if err:
        return err
    try:
        svc.heartbeat(session_id=session_id, user_id=user_id)
        return jsonify({"success": True}), 200
    except Exception:
        return internal_error(logger, "heartbeat")


# ── Queries ─────────────────────────────────────────────────────────

@collaboration_bp.route("/session.participants", methods=["GET"])
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def get_participants(session_id):
    svc, err = service_or_unavailable()
    if err:
        return err
    try:
        participants = svc.get_participants(session_id)
        return jsonify(participants.model_dump(mode="json")), 200
    except Exception:
        return internal_error(logger, "get_participants")


@collaboration_bp.route("/team.sessions", methods=["GET"])
@from_query({
    "team_id": fields.Str(data_key="teamId", required=True),
})
def get_team_sessions(team_id):
    svc, err = service_for_team(team_id)
    if err:
        return err
    try:
        index = svc.get_team_sessions(team_id)
        return jsonify(index.model_dump(mode="json")), 200
    except Exception:
        return internal_error(logger, "get_team_sessions")


@collaboration_bp.route("/user.active_sessions", methods=["GET"])
@from_query({
    "user_id": fields.Str(data_key="userId", required=True),
})
def get_user_active_sessions(user_id):
    svc, err = service_for_user(user_id)
    if err:
        return err
    try:
        session_ids = svc.get_user_active_sessions(user_id)
        return jsonify({"userId": user_id, "activeSessions": session_ids}), 200
    except Exception:
        return internal_error(logger, "get_user_active_sessions")


# ── Typing indicators ────────────────────────────────────────────

@collaboration_bp.route("/session.typing", methods=["POST"])
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "user_id": fields.Str(data_key="userId", required=True),
    "is_typing": fields.Bool(data_key="isTyping", load_default=True),
})
def set_typing(session_id, user_id, is_typing):
    svc, err = service_for_user(user_id)
    if err:
        return err
    try:
        if is_typing:
            svc.set_typing(session_id=session_id, user_id=user_id)
        else:
            svc.clear_typing(session_id=session_id, user_id=user_id)
        return jsonify({"success": True}), 200
    except Exception:
        return internal_error(logger, "set_typing")


@collaboration_bp.route("/session.typing", methods=["GET"])
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def get_typing(session_id):
    svc, err = service_or_unavailable()
    if err:
        return err
    try:
        users = svc.get_typing_users(session_id)
        return jsonify({"sessionId": session_id, "typingUsers": users}), 200
    except Exception:
        return internal_error(logger, "get_typing")


@collaboration_bp.route("/health", methods=["GET"])
def collaboration_health():
    svc, err = service_or_unavailable()
    if err:
        return jsonify({"available": False, "reason": "not_configured"}), 200
    return jsonify({"available": svc.is_available()}), 200
