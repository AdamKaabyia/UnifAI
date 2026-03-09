from flask import Blueprint, jsonify, current_app
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields

teams_bp = Blueprint("teams", __name__)


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
