from flask import Blueprint, jsonify, current_app, request

team_bp = Blueprint("teams", __name__)


@team_bp.route("/team.create", methods=["POST"])
def create_team():
    svc = current_app.extensions["team_service"]
    body = request.get_json(silent=True) or {}

    name = body.get("name")
    created_by = body.get("createdBy")
    members = body.get("members", [])

    if not name or not created_by:
        return jsonify({"error": "name and createdBy are required"}), 400

    try:
        team = svc.create(name=name, created_by=created_by, members=members)
        return jsonify(team.model_dump(mode="json")), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@team_bp.route("/teams.list", methods=["GET"])
def list_teams():
    svc = current_app.extensions["team_service"]
    user_id = request.args.get("userId", "").strip()
    if not user_id:
        return jsonify({"error": "userId parameter is required"}), 400

    try:
        teams = svc.list_user_teams(user_id)
        return jsonify({"teams": [t.model_dump(mode="json") for t in teams]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@team_bp.route("/team.get", methods=["GET"])
def get_team():
    svc = current_app.extensions["team_service"]
    team_id = request.args.get("teamId", "").strip()
    if not team_id:
        return jsonify({"error": "teamId parameter is required"}), 400

    try:
        team = svc.get(team_id)
        return jsonify(team.model_dump(mode="json")), 200
    except KeyError:
        return jsonify({"error": "Team not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@team_bp.route("/team.update", methods=["PUT"])
def update_team():
    svc = current_app.extensions["team_service"]
    body = request.get_json(silent=True) or {}

    team_id = body.get("teamId")
    if not team_id:
        return jsonify({"error": "teamId is required"}), 400

    try:
        team = svc.update(
            team_id=team_id,
            name=body.get("name"),
            members=body.get("members"),
        )
        return jsonify(team.model_dump(mode="json")), 200
    except KeyError:
        return jsonify({"error": "Team not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@team_bp.route("/team.delete", methods=["DELETE"])
def delete_team():
    svc = current_app.extensions["team_service"]
    team_id = request.args.get("teamId", "").strip()
    if not team_id:
        return jsonify({"error": "teamId parameter is required"}), 400

    try:
        svc.delete(team_id)
        return jsonify({"status": "deleted"}), 200
    except KeyError:
        return jsonify({"error": "Team not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
