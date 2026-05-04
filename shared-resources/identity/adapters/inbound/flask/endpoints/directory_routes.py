import logging

from flask import Blueprint, jsonify, current_app, request

from utils.auth_manager import directory_request_user_token

logger = logging.getLogger(__name__)

directory_bp = Blueprint("directory", __name__)


def _parse_limit(default: int = 20) -> int:
    try:
        return int(request.args.get("limit", default))
    except (ValueError, TypeError):
        return default


def _user_token():
    return directory_request_user_token()


@directory_bp.route("/directory.status", methods=["GET"])
def directory_status():
    svc = current_app.extensions["team_service"]
    return jsonify({"enabled": svc.has_directory}), 200


@directory_bp.route("/directory.search_users", methods=["GET"])
def search_users():
    svc = current_app.extensions["team_service"]
    if not svc.has_directory:
        return jsonify({"error": "No directory provider configured"}), 501

    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "q parameter is required"}), 400

    limit = _parse_limit()
    try:
        users = svc.search_directory_users(q, limit=limit, user_token=_user_token())
        return jsonify({"users": [u.model_dump(mode="json") for u in users]}), 200
    except Exception:
        logger.exception("search_users failed")
        return jsonify({"error": "Internal server error"}), 500


@directory_bp.route("/directory.search_groups", methods=["GET"])
def search_groups():
    svc = current_app.extensions["team_service"]
    if not svc.has_directory:
        return jsonify({"error": "No directory provider configured"}), 501

    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "q parameter is required"}), 400

    limit = _parse_limit()
    try:
        groups = svc.search_directory_groups(q, limit=limit, user_token=_user_token())
        return jsonify({"groups": [g.model_dump(mode="json") for g in groups]}), 200
    except Exception:
        logger.exception("search_groups failed")
        return jsonify({"error": "Internal server error"}), 500


@directory_bp.route("/directory.search", methods=["GET"])
def search_all():
    """Unified search returning both users and groups."""
    svc = current_app.extensions["team_service"]
    if not svc.has_directory:
        return jsonify({"error": "No directory provider configured"}), 501

    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "q parameter is required"}), 400

    limit = _parse_limit()
    token = _user_token()
    try:
        users = svc.search_directory_users(q, limit=limit, user_token=token)
        groups = svc.search_directory_groups(q, limit=limit, user_token=token)
        return jsonify({
            "users": [u.model_dump(mode="json") for u in users],
            "groups": [g.model_dump(mode="json") for g in groups],
        }), 200
    except Exception:
        logger.exception("search_all failed")
        return jsonify({"error": "Internal server error"}), 500


@directory_bp.route("/directory.get_user", methods=["GET"])
def get_user():
    svc = current_app.extensions["team_service"]
    if not svc.has_directory:
        return jsonify({"error": "No directory provider configured"}), 501

    user_id = request.args.get("userId", "").strip()
    if not user_id:
        return jsonify({"error": "userId parameter is required"}), 400

    try:
        user = svc.get_directory_user(user_id, user_token=_user_token())
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify(user.model_dump(mode="json")), 200
    except Exception:
        logger.exception("get_user failed")
        return jsonify({"error": "Internal server error"}), 500


@directory_bp.route("/directory.get_group", methods=["GET"])
def get_group():
    svc = current_app.extensions["team_service"]
    if not svc.has_directory:
        return jsonify({"error": "No directory provider configured"}), 501

    group_id = request.args.get("groupId", "").strip()
    if not group_id:
        return jsonify({"error": "groupId parameter is required"}), 400

    try:
        group = svc.get_directory_group(group_id, user_token=_user_token())
        if not group:
            return jsonify({"error": "Group not found"}), 404
        return jsonify(group.model_dump(mode="json")), 200
    except Exception:
        logger.exception("get_group failed")
        return jsonify({"error": "Internal server error"}), 500
