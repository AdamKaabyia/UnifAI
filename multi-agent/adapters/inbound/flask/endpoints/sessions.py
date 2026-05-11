from flask import Blueprint, jsonify, current_app, Response, request
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields
import json
from pydantic.json import pydantic_encoder
from mas.core.channels import with_heartbeats
from mas.session.domain.exceptions import BlueprintNotFoundError
from inbound.flask.decorators import require_identity_authorization, with_identity

sessions_bp = Blueprint("sessions", __name__)


def _acting_user_for_credentials(logged_in_user: str) -> str:
    """Body wins; else UI agent client sends ``X-Authenticated-User`` (see axiosAgentConfig)."""
    v = (logged_in_user or "").strip()
    if v:
        return v
    return (request.headers.get("X-Authenticated-User") or "").strip()


@sessions_bp.route("/user.session.create", methods=["POST"])
@require_identity_authorization
@with_identity
@from_body({
    "blueprint_id": fields.Str(data_key="blueprintId", required=True),
    "metadata": fields.Dict(data_key="metadata", required=False, load_default=lambda: {}, dump_default=lambda: {})
})
def create_user_session(identity, blueprint_id, metadata):
    try:
        session_svc = current_app.container.session_service
        run_id = session_svc.create(identity=identity,
                                    blueprint_id=blueprint_id,
                                    metadata=metadata)
        return jsonify(run_id), 200
    except BlueprintNotFoundError as e:
        return jsonify({
            "error": str(e),
            "error_type": "BLUEPRINT_NOT_FOUND",
            "blueprint_id": e.blueprint_id
        }), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/user.session.execute", methods=["POST"])
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "inputs": fields.Dict(data_key="inputs", required=True),
    "stream_mode": fields.List(fields.Str(), data_key="streamMode", load_default=lambda: ["custom"]),
    "stream": fields.Bool(data_key="stream", load_default=False),
    "scope": fields.Str(data_key="scope", load_default="public"),
    "logged_in_user": fields.Str(data_key="loggedInUser", required=False, load_default=lambda: "")
})
def execute_user_session(session_id, inputs, stream_mode, stream, scope, logged_in_user):
    """
    Execute (or stream) an existing session.
    - If `stream` is False (default), returns the full result as JSON.
    - If `stream` is True, returns an NDJSON stream of channel events.
    """
    logged_in_user = _acting_user_for_credentials(logged_in_user)
    svc = current_app.container.session_service
    try:
        status = svc.get_status(session_id)
    except Exception:
        status = None
    if status in ("QUEUED", "RUNNING"):
        return jsonify({"error": f"Session {session_id} is already {status}"}), 409

    if not stream:
        result = svc.run(
            session_id=session_id,
            inputs=inputs,
            scope=scope,
            logged_in_user=logged_in_user,
        )
        return json.dumps(result, default=pydantic_encoder), 200

    def generate():
        stream_iter = svc.run(
            session_id=session_id,
            inputs=inputs,
            scope=scope,
            stream=True,
            logged_in_user=logged_in_user,
        )
        for chunk in with_heartbeats(stream_iter):
            yield json.dumps(chunk, default=pydantic_encoder) + "\n"

    resp = Response(
        generate(),
        mimetype="application/x-ndjson",
    )
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


@sessions_bp.route("/user.session.submit", methods=["POST"])
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "inputs": fields.Dict(data_key="inputs", required=True),
    "scope": fields.Str(data_key="scope", load_default="public"),
    "logged_in_user": fields.Str(data_key="loggedInUser", required=False, load_default=lambda: "")
})
def submit_user_session(session_id, inputs, scope, logged_in_user):
    """
    Fire-and-forget execute for Temporal-backed sessions.
    Starts the Temporal workflow in the background and returns HTTP 202
    immediately with the workflow_id – no blocking until completion.

    Poll /session.status.get?sessionId=<id> for status updates.
    """
    try:
        logged_in_user = _acting_user_for_credentials(logged_in_user)
        svc = current_app.container.session_service
        workflow_id = svc.submit(
            session_id=session_id,
            inputs=inputs,
            scope=scope,
            logged_in_user=logged_in_user,
        )
        return jsonify({"sessionId": session_id, "workflowId": workflow_id}), 202
    except TypeError as e:
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.state.get", methods=["GET"])
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def get_session_state(session_id):
    try:
        svc = current_app.container.session_service
        state = svc.get_state(run_id=session_id)
        return jsonify(state), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.chat.get", methods=["GET"])
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def get_session_chat(session_id):
    try:
        svc = current_app.container.session_service
        chat = svc.get_chat(run_id=session_id)
        return jsonify(chat.model_dump(mode="json")), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.status.get", methods=["GET"])
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def get_session_status(session_id):
    try:
        svc = current_app.container.session_service
        status = svc.get_status(run_id=session_id)
        return jsonify(status), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.user.list", methods=["GET"])
@require_identity_authorization
@with_identity
def list_user_sessions(identity):
    try:
        svc = current_app.container.session_service
        return jsonify(svc.list_user_sessions(identity)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.user.blueprints.get", methods=["GET"])
@require_identity_authorization
@with_identity
def get_user_blueprints(identity):
    try:
        svc = current_app.container.session_service
        return jsonify(svc.get_user_blueprints(identity)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.delete", methods=["DELETE"])
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def delete_session(session_id):
    """
    Delete a session by session_id.
    Returns success: true if deleted, false if not found.
    """
    # TODO: Add authorization check - verify user has permission to delete this session
    try:
        svc = current_app.container.session_service
        deleted = svc.delete(run_id=session_id)
        return jsonify({"success": deleted}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- Stream monitoring ----------

@sessions_bp.route("/session.stream.status", methods=["GET"])
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def get_stream_status(session_id):
    """Return metadata about a session's event stream."""
    monitor = current_app.container.channel_factory.create_monitor()
    if monitor is None or not monitor.is_available():
        return jsonify({"error": "Stream monitoring not available — no distributed channel configured"}), 501
    try:
        status = monitor.get_status(session_id)
        if status is None:
            return jsonify({"error": f"Session {session_id} not found in stream"}), 404
        return jsonify(status), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.stream.active", methods=["GET"])
def list_active_streams():
    """List all currently active (running) session streams."""
    monitor = current_app.container.channel_factory.create_monitor()
    if monitor is None or not monitor.is_available():
        return jsonify({"error": "Stream monitoring not available — no distributed channel configured"}), 501
    try:
        active = monitor.list_active()
        return jsonify({"active_sessions": active, "count": len(active)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.subscribe", methods=["GET"])
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def subscribe_session(session_id):
    """
    Stream session events as NDJSON.
    Late-joining clients receive the full event history (replay)
    followed by live events.
    """
    factory = current_app.container.channel_factory
    reader = factory.create_reader(session_id)

    if reader is None:
        return jsonify({"error": "Streaming subscribe not available — no distributed channel configured"}), 501

    def generate():
        try:
            for event in with_heartbeats(reader):
                yield json.dumps(event, default=pydantic_encoder) + "\n"
        finally:
            reader.close()

    resp = Response(
        generate(),
        mimetype="application/x-ndjson",
    )
    resp.headers["X-Accel-Buffering"] = "no"
    return resp
