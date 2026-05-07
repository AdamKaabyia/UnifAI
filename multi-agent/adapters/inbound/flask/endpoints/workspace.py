import logging
import secrets

from flask import Blueprint, jsonify, current_app, request
from global_utils.helpers.apiargs import from_body
from webargs import fields
from mas.core.identity import Identity, IdentityType

logger = logging.getLogger(__name__)

workspace_bp = Blueprint("workspace", __name__)

_CLEANUP_SECRET_HEADER = "X-Internal-Secret"


@workspace_bp.route("/workspace.cleanup", methods=["DELETE"])
@from_body({
    "identity_type": fields.Str(data_key="identityType", required=True),
    "identity_id": fields.Str(data_key="identityId", required=True),
})
def cleanup_workspace(identity_type, identity_id):
    """Delete all resources, blueprints, and sessions owned by an identity.

    Intended for team deletion cascade — the SSO backend deletes the team
    record, this endpoint removes everything the team owned in multi-agent.

    Protected by a shared secret header so only trusted internal callers
    (e.g. the SSO backend) can invoke it.
    """
    cleanup_secret = current_app.config.get("cleanup_secret", "")
    if not cleanup_secret:
        logger.error("workspace.cleanup called but cleanup_secret is not configured")
        return jsonify({"error": "Endpoint not configured"}), 503

    provided = str(request.headers.get(_CLEANUP_SECRET_HEADER, "") or "")
    secret = str(cleanup_secret or "")
    if not secrets.compare_digest(provided, secret):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        id_type = IdentityType(identity_type)
    except ValueError:
        return jsonify({"error": f"Invalid identityType: {identity_type}"}), 400

    identity = Identity(type=id_type, id=identity_id)

    container = current_app.container
    resources_deleted = container.resource_repo.delete_by_identity(identity)
    blueprints_deleted = container.blueprint_repo.delete_by_identity(identity)
    sessions_deleted = container.session_repo.delete_by_identity(identity)

    logger.info(
        "workspace.cleanup identity=%s/%s deleted resources=%d blueprints=%d sessions=%d",
        identity_type, identity_id,
        resources_deleted, blueprints_deleted, sessions_deleted,
    )

    return jsonify({
        "status": "cleaned",
        "identity": {"type": identity_type, "id": identity_id},
        "deleted": {
            "resources": resources_deleted,
            "blueprints": blueprints_deleted,
            "sessions": sessions_deleted,
        },
    }), 200
