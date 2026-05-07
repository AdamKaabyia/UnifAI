from flask import Blueprint, jsonify, current_app
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields
from mas.sharing.models import ShareItemKind, ShareStatus
from inbound.flask.decorators import with_identity

shares_bp = Blueprint("shares", __name__)


@shares_bp.route("/share.create", methods=["POST"])
@from_body({
    "recipient_user_id": fields.Str(data_key="recipientUserId", required=True),
    "item_kind": fields.Str(data_key="itemKind", required=True),
    "item_id": fields.Str(data_key="itemId", required=True),
    "message": fields.Str(required=False),
    "sender_user_id": fields.Str(data_key="senderUserId", required=False, load_default="alice"),
    "sender_type": fields.Str(data_key="senderType", required=False, load_default="user"),
    "sender_display_name": fields.Str(data_key="senderDisplayName", required=False),
    "auto_accept": fields.Bool(data_key="autoAccept", required=False, load_default=False),
})
def create_share(
    recipient_user_id,
    item_kind,
    item_id,
    message=None,
    sender_user_id="alice",
    sender_type="user",
    sender_display_name=None,
    auto_accept=False,
):
    """Create share invitation."""
    try:
        # Validate item_kind
        try:
            kind = ShareItemKind(item_kind)
        except ValueError:
            return jsonify({"error": "Invalid itemKind. Must be 'resource' or 'blueprint'"}), 400

        directory = current_app.container.directory_provider
        if directory:
            resolved = directory.get_user(recipient_user_id)
            if not resolved:
                return jsonify({"error": f"Recipient '{recipient_user_id}' not found in directory"}), 400

        svc = current_app.container.share_service
        share_id = svc.create_invite(
            sender_user_id=sender_user_id,
            recipient_user_id=recipient_user_id,
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
            result = svc.accept_invite(share_id, recipient_user_id=recipient_user_id)
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
    "recipient_user_id": fields.Str(data_key="recipientUserId", required=False, load_default="alice")
})
def accept_share(share_id, recipient_user_id="alice"):
    """Accept share invitation."""
    try:
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
    "recipient_user_id": fields.Str(data_key="recipientUserId", required=False, load_default="alice")
})
def decline_share(share_id, recipient_user_id="alice"):
    """Decline share invitation."""
    try:
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
    "sender_user_id": fields.Str(data_key="senderUserId", required=True),
    "team_name": fields.Str(data_key="teamName", required=True),
    "item_kind": fields.Str(data_key="itemKind", required=True),
    "item_id": fields.Str(data_key="itemId", required=True),
})
def share_to_team(sender_user_id, team_name, item_kind, item_id):
    """Share item directly to a team workspace."""
    try:
        try:
            kind = ShareItemKind(item_kind)
        except ValueError:
            return jsonify({"error": "Invalid itemKind. Must be 'resource' or 'blueprint'"}), 400

        svc = current_app.container.share_service
        result = svc.share_to_team(
            sender_user_id=sender_user_id,
            team_name=team_name,
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
    "sender_user_id": fields.Str(data_key="senderUserId", required=False, load_default="alice")
})
def cancel_share(share_id, sender_user_id="alice"):
    """Cancel share invitation."""
    try:
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
            payload["sender_user_id"] = invite.sender_identity.display_name or invite.sender_identity.id
            payload["recipient_user_id"] = invite.recipient_identity.display_name or invite.recipient_identity.id
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
    "user_id": fields.Str(data_key="userId", required=False, load_default="alice")
})
def get_share(share_id, user_id="alice"):
    """Get share invitation details."""
    try:
        svc = current_app.container.share_service
        invite = svc.get_invite(share_id)

        # Check authorization
        if invite.sender_identity.id != user_id and invite.recipient_identity.id != user_id:
            return jsonify({"error": "Not authorized to view this invitation"}), 403

        payload = invite.model_dump(mode="json")
        payload["sender_user_id"] = invite.sender_identity.display_name or invite.sender_identity.id
        payload["recipient_user_id"] = invite.recipient_identity.display_name or invite.recipient_identity.id
        return jsonify(payload), 200

    except KeyError:
        return jsonify({"error": "Share invitation not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
