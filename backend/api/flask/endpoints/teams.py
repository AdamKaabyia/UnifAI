from flask import Blueprint, jsonify, current_app, request
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields


def _user_token():
    return request.headers.get("X-User-Token")

teams_bp = Blueprint("teams", __name__)


# ────────────────────────── local team CRUD ──────────────────────────


@teams_bp.route("/team.create", methods=["POST"])
@from_body({
    "name": fields.Str(required=True),
    "created_by": fields.Str(data_key="createdBy", required=True),
    "members": fields.List(fields.Str(), required=True),
})
def create_team(name, created_by, members):
    svc = current_app.container.team_service
    try:
        team = svc.create(name=name, created_by=created_by, members=members)
        return jsonify(team.model_dump(mode="json")), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@teams_bp.route("/teams.list", methods=["GET"])
@from_query({
    "user_id": fields.Str(data_key="userId", required=True),
})
def list_teams(user_id):
    svc = current_app.container.team_service
    try:
        teams = svc.list_user_teams(user_id)
        return jsonify({
            "teams": [t.model_dump(mode="json") for t in teams]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@teams_bp.route("/team.get", methods=["GET"])
@from_query({
    "team_id": fields.Str(data_key="teamId", required=True),
})
def get_team(team_id):
    svc = current_app.container.team_service
    try:
        team = svc.get(team_id)
        return jsonify(team.model_dump(mode="json")), 200
    except KeyError:
        return jsonify({"error": "Team not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@teams_bp.route("/team.update", methods=["PUT"])
@from_body({
    "team_id": fields.Str(data_key="teamId", required=True),
    "name": fields.Str(required=False),
    "members": fields.List(fields.Str(), required=False),
})
def update_team(team_id, name=None, members=None):
    svc = current_app.container.team_service
    try:
        team = svc.update(team_id=team_id, name=name, members=members)
        return jsonify(team.model_dump(mode="json")), 200
    except KeyError:
        return jsonify({"error": "Team not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@teams_bp.route("/team.delete", methods=["DELETE"])
@from_query({
    "team_id": fields.Str(data_key="teamId", required=True),
})
def delete_team(team_id):
    svc = current_app.container.team_service
    try:
        svc.delete(team_id)
        return jsonify({"status": "deleted"}), 200
    except KeyError:
        return jsonify({"error": "Team not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ───────────────── directory provider endpoints ──────────────────────


@teams_bp.route("/directory.status", methods=["GET"])
def directory_status():
    svc = current_app.container.team_service
    return jsonify({"enabled": svc.has_directory}), 200


@teams_bp.route("/directory.search_users", methods=["GET"])
@from_query({
    "q": fields.Str(required=True),
    "limit": fields.Int(required=False, load_default=20),
})
def directory_search_users(q, limit):
    svc = current_app.container.team_service
    if not svc.has_directory:
        return jsonify({"error": "No directory provider configured"}), 501
    try:
        users = svc.search_directory_users(q, limit=limit, user_token=_user_token())
        return jsonify({
            "users": [u.model_dump(mode="json") for u in users],
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@teams_bp.route("/directory.get_user", methods=["GET"])
@from_query({
    "user_id": fields.Str(data_key="userId", required=True),
})
def directory_get_user(user_id):
    svc = current_app.container.team_service
    if not svc.has_directory:
        return jsonify({"error": "No directory provider configured"}), 501
    try:
        user = svc.get_directory_user(user_id, user_token=_user_token())
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify(user.model_dump(mode="json")), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
