from flask import Blueprint, jsonify, current_app, request
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields
from mas.core.identity import IdentityType
from mas.sharing.models import ShareItemKind, ShareStatus
from mas.sharing.service import ShareService
from inbound.flask.decorators import with_identity, _is_team_member, _resolve_team_id_for_member

shares_bp = Blueprint("shares", __name__)


@shares_bp.route("/share.create", methods=["POST"])
@from_body({
    "recipient_user_id": fields.Str(data_key="recipientUserId", required=True),
    "item_kind": fields.Str(data_key="itemKind", required=True),
    "item_id": fields.Str(data_key="itemId", required=True),
    "message": fields.Str(required=False),
    "sender_type": fields.Str(data_key="senderType", required=False, load_default="user"),
    "sender_display_name": fields.Str(data_key="senderDisplayName", required=False),
    "sender_identity_id": fields.Str(data_key="senderIdentityId", required=False),
    "auto_accept": fields.Bool(data_key="autoAccept", required=False, load_default=False),
})
def create_share(
    recipient_user_id,
    item_kind,
    item_id,
    message=None,
    sender_type="user",
    sender_display_name=None,
    sender_identity_id=None,
    auto_accept=False,
):
    """Create share invitation."""
    try:
        authenticated = request.headers.get("X-Authenticated-User", "").strip()
        if not authenticated:
            return jsonify({"error": "Missing authenticated user"}), 401

        sender_type_norm = str(sender_type or "user").strip().lower()
        claimed_owner = str(sender_identity_id or "").strip()
        if sender_type_norm == "team":
            if not claimed_owner:
                return jsonify(
                    {"error": "senderIdentityId (team id) is required when senderType is team"},
                ), 400
            if not _is_team_member(authenticated, claimed_owner):
                return jsonify({"error": "Not authorized to share as this team"}), 403
            effective_sender_id = claimed_owner
        else:
            if claimed_owner and claimed_owner.casefold() != authenticated.casefold():
                return jsonify(
                    {"error": "senderIdentityId must match the authenticated user for personal shares"},
                ), 403
            effective_sender_id = authenticated

        # Validate item_kind
        try:
            kind = ShareItemKind(item_kind)
        except ValueError:
            return jsonify({"error": "Invalid itemKind. Must be 'resource' or 'blueprint'"}), 400

        recipient_raw = str(recipient_user_id).strip()

        directory = current_app.container.directory_provider
        if directory and recipient_raw.casefold() != authenticated.casefold():
            resolved = directory.get_user(recipient_raw)
            if not resolved:
                return jsonify({"error": f"Recipient '{recipient_raw}' not found in directory"}), 400

        # Auto-accept self-copy: persist recipient as the canonical auth header value so
        # accept_invite(..., recipient_user_id=X-Authenticated-User) always matches.
        recipient_effective = (
            authenticated
            if (auto_accept and recipient_raw.casefold() == authenticated.casefold())
            else recipient_raw
        )

        svc = current_app.container.share_service
        share_id = svc.create_invite(
            sender_user_id=effective_sender_id,
            recipient_user_id=recipient_effective,
            item_kind=kind,
            item_id=item_id,
            message=message,
            sender_type=sender_type,
            sender_display_name=sender_display_name,
        )

        response = {
            "status": "success",
            "share_id": share_id
        }
        if auto_accept:
            result = svc.accept_invite(share_id, recipient_user_id=recipient_effective)
            response["result"] = result.model_dump(mode="json")
            response["auto_accepted"] = True

        return jsonify(response), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shares_bp.route("/share.accept", methods=["POST"])
@from_body({
    "share_id": fields.Str(data_key="shareId", required=True),
})
def accept_share(share_id):
    """Accept share invitation."""
    try:
        recipient_user_id = request.headers.get("X-Authenticated-User", "").strip()
        if not recipient_user_id:
            return jsonify({"error": "Missing authenticated user"}), 401

        svc = current_app.container.share_service
        result = svc.accept_invite(share_id, recipient_user_id=recipient_user_id)

        return jsonify({
            "status": "success",
            "result": result.model_dump(mode="json")
        }), 200

    except KeyError:
        return jsonify({"error": "Share invitation not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shares_bp.route("/share.decline", methods=["POST"])
@from_body({
    "share_id": fields.Str(data_key="shareId", required=True),
})
def decline_share(share_id):
    """Decline share invitation."""
    try:
        recipient_user_id = request.headers.get("X-Authenticated-User", "").strip()
        if not recipient_user_id:
            return jsonify({"error": "Missing authenticated user"}), 401

        svc = current_app.container.share_service
        svc.decline_invite(share_id, recipient_user_id=recipient_user_id)

        return jsonify({"status": "success"}), 200

    except KeyError:
        return jsonify({"error": "Share invitation not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shares_bp.route("/share.to_team", methods=["POST"])
@from_body({
    "team_name": fields.Str(data_key="teamName", required=True),
    "item_kind": fields.Str(data_key="itemKind", required=True),
    "item_id": fields.Str(data_key="itemId", required=True),
})
def share_to_team(team_name, item_kind, item_id):
    """Share item directly to a team workspace."""
    try:
        sender_user_id = request.headers.get("X-Authenticated-User", "").strip()
        if not sender_user_id:
            return jsonify({"error": "Missing authenticated user"}), 401
        team_id = _resolve_team_id_for_member(sender_user_id, team_name)
        if team_id is None:
            return jsonify({"error": "Not authorized to share to this team"}), 403

        try:
            kind = ShareItemKind(item_kind)
        except ValueError:
            return jsonify({"error": "Invalid itemKind. Must be 'resource' or 'blueprint'"}), 400

        svc = current_app.container.share_service
        result = svc.share_to_team(
            sender_user_id=sender_user_id,
            team_name=team_id,
            item_kind=kind,
            item_id=item_id
        )

        return jsonify({
            "status": "success",
            "result": result.model_dump(mode="json")
        }), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shares_bp.route("/share.cancel", methods=["POST"])
@from_body({
    "share_id": fields.Str(data_key="shareId", required=True),
})
def cancel_share(share_id):
    """Cancel share invitation."""
    try:
        sender_user_id = request.headers.get("X-Authenticated-User", "").strip()
        if not sender_user_id:
            return jsonify({"error": "Missing authenticated user"}), 401

        svc = current_app.container.share_service
        svc.cancel_invite(share_id, sender_user_id=sender_user_id)

        return jsonify({"status": "success"}), 200

    except KeyError:
        return jsonify({"error": "Share invitation not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shares_bp.route("/shares.list", methods=["GET"])
@with_identity
@from_query({
    "direction": fields.Str(required=False, load_default="received"),
    "status": fields.Str(required=False),
    "skip": fields.Int(required=False, load_default=0),
    "limit": fields.Int(required=False, load_default=100),
})
def list_shares(identity, direction="received", status=None, skip=0, limit=100):
    """List share invitations."""
    try:
        status_enum = None
        if status:
            try:
                status_enum = ShareStatus(status)
            except ValueError:
                return jsonify({"error": "Invalid status"}), 400

        svc = current_app.container.share_service

        if direction == "received":
            invites = svc.list_received_invites(identity, status_enum, skip, limit)
        elif direction == "sent":
            invites = svc.list_sent_invites(identity, status_enum, skip, limit)
        else:
            return jsonify({"error": "Direction must be 'received' or 'sent'"}), 400

        def serialize_invite(invite):
            payload = invite.model_dump(mode="json")
            payload["sender_user_id"] = invite.sender_identity.id
            payload["sender_display_name"] = invite.sender_identity.display_name
            payload["recipient_user_id"] = invite.recipient_identity.id
            payload["recipient_display_name"] = invite.recipient_identity.display_name
            return payload

        return jsonify({
            "invites": [serialize_invite(invite) for invite in invites],
            "count": len(invites)
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shares_bp.route("/share.get", methods=["GET"])
@from_query({
    "share_id": fields.Str(data_key="shareId", required=True),
})
def get_share(share_id):
    """Get share invitation details."""
    try:
        user_id = request.headers.get("X-Authenticated-User", "").strip()
        if not user_id:
            return jsonify({"error": "Missing authenticated user"}), 401

        svc = current_app.container.share_service
        invite = svc.get_invite(share_id)

        # Check authorization: sender (user or team member), or recipient
        sender_ok = (
            invite.sender_identity.type == IdentityType.TEAM
            and _is_team_member(user_id, invite.sender_identity.id)
        ) or ShareService._principal_matches_identity(invite.sender_identity, user_id)
        recipient_ok = ShareService._principal_matches_identity(
            invite.recipient_identity, user_id
        )
        if not (sender_ok or recipient_ok):
            return jsonify({"error": "Not authorized to view this invitation"}), 403

        payload = invite.model_dump(mode="json")
        payload["sender_user_id"] = invite.sender_identity.id
        payload["sender_display_name"] = invite.sender_identity.display_name
        payload["recipient_user_id"] = invite.recipient_identity.id
        payload["recipient_display_name"] = invite.recipient_identity.display_name
        return jsonify(payload), 200

    except KeyError:
        return jsonify({"error": "Share invitation not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
