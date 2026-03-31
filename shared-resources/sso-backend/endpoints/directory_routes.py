from flask import Blueprint, jsonify, current_app, request

directory_bp = Blueprint("directory", __name__)


def _get_directory_provider():
    return current_app.extensions.get('directory_provider')


@directory_bp.route("/directory.status", methods=["GET"])
def directory_status():
    provider = _get_directory_provider()
    return jsonify({"enabled": provider is not None}), 200


@directory_bp.route("/directory.search_users", methods=["GET"])
def search_users():
    provider = _get_directory_provider()
    if not provider:
        return jsonify({"error": "No directory provider configured"}), 501

    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "q parameter is required"}), 400

    limit = int(request.args.get("limit", 20))
    try:
        users = provider.search_users(q, limit=limit)
        return jsonify({"users": [u.model_dump(mode="json") for u in users]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@directory_bp.route("/directory.search", methods=["GET"])
def search_all():
    """Unified search returning both users and groups."""
    provider = _get_directory_provider()
    if not provider:
        return jsonify({"error": "No directory provider configured"}), 501

    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "q parameter is required"}), 400

    limit = int(request.args.get("limit", 20))
    try:
        users = provider.search_users(q, limit=limit)
        groups = provider.search_groups(q, limit=limit)
        return jsonify({
            "users": [u.model_dump(mode="json") for u in users],
            "groups": [g.model_dump(mode="json") for g in groups],
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@directory_bp.route("/directory.get_user", methods=["GET"])
def get_user():
    provider = _get_directory_provider()
    if not provider:
        return jsonify({"error": "No directory provider configured"}), 501

    user_id = request.args.get("userId", "").strip()
    if not user_id:
        return jsonify({"error": "userId parameter is required"}), 400

    try:
        user = provider.get_user(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify(user.model_dump(mode="json")), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@directory_bp.route("/directory.get_group", methods=["GET"])
def get_group():
    provider = _get_directory_provider()
    if not provider:
        return jsonify({"error": "No directory provider configured"}), 501

    group_id = request.args.get("groupId", "").strip()
    if not group_id:
        return jsonify({"error": "groupId parameter is required"}), 400

    try:
        group = provider.get_group(group_id)
        if not group:
            return jsonify({"error": "Group not found"}), 404
        return jsonify(group.model_dump(mode="json")), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
