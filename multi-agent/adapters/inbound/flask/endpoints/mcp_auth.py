"""
Flask endpoints for the auth callback lifecycle.

Routes:
  POST /api/mcp-auth/exchange   — Exchange auth code for tokens (internal, from SSO pod)
  GET  /api/mcp-auth/status     — Check token status for a user + server
"""

from flask import Blueprint, jsonify, request, current_app
from global_utils.helpers.apiargs import from_body, from_query
from global_utils.utils.async_bridge import get_async_bridge
from webargs import fields

mcp_auth_bp = Blueprint("mcp_auth", __name__)


@mcp_auth_bp.route("/exchange", methods=["POST"])
@from_body({
    "code": fields.Str(required=True),
    "state": fields.Str(required=True),
})
def exchange_code(code, state):
    """
    Exchange an authorization code for tokens.

    Called by the SSO pod after receiving the OAuth callback.
    Protected by internal service token validation.
    """
    internal_token = request.headers.get("X-Internal-Service-Token", "")
    expected_token = getattr(current_app.container, "internal_service_token", "")

    if not expected_token:
        return jsonify({"error": "Internal service token not configured"}), 500

    if internal_token != expected_token:
        return jsonify({"error": "Unauthorized — invalid internal service token"}), 403

    try:
        svc = current_app.container.auth_exchange_service
        with get_async_bridge() as bridge:
            result = bridge.run(svc.exchange(code=code, state=state))
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@mcp_auth_bp.route("/status", methods=["GET"])
@from_query({
    "user_id": fields.Str(data_key="userId", required=True),
    "server_identifier": fields.Str(data_key="serverIdentifier", required=True),
})
def token_status(user_id, server_identifier):
    """Check whether a user has a valid credential for an auth server."""
    try:
        store = current_app.container.token_store
        cred = store.find_by_server(user_id=user_id, server_identifier=server_identifier)
        if cred and cred.is_valid():
            return jsonify({
                "authenticated": True,
                "status": "active",
                "expires_at": cred.expires_at.isoformat() if cred.expires_at else None,
            }), 200
        return jsonify({
            "authenticated": False,
            "status": "expired" if cred else "not_found",
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
