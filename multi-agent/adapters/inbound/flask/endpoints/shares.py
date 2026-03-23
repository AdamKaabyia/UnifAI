from flask import Blueprint, jsonify, current_app
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields
from mas.sharing.models import ShareItemKind, ShareStatus

shares_bp = Blueprint("shares", __name__)


@shares_bp.route("/share.create", methods=["POST"])
@from_body({
    "recipient_user_id": fields.Str(data_key="recipientUserId", required=True),
    "item_kind": fields.Str(data_key="itemKind", required=True),
    "item_id": fields.Str(data_key="itemId", required=True),
    "message": fields.Str(required=False),
    "sender_user_id": fields.Str(data_key="senderUserId", required=False, load_default="alice")
})
def create_share(recipient_user_id, item_kind, item_id, message=None, sender_user_id="alice"):
    """Create share invitation."""
    try:
        # Validate item_kind
        try:
            kind = ShareItemKind(item_kind)
        except ValueError:
            return jsonify({"error": "Invalid itemKind. Must be 'resource' or 'blueprint'"}), 400

        svc = current_app.container.share_service
        share_id = svc.create_invite(
            sender_user_id=sender_user_id,
            recipient_user_id=recipient_user_id,
            item_kind=kind,
            item_id=item_id,
            message=message
        )

        return jsonify({
            "status": "success",
            "share_id": share_id
        }), 201

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
@from_query({
    "direction": fields.Str(required=False, load_default="received"),
    "status": fields.Str(required=False),
    "skip": fields.Int(required=False, load_default=0),
    "limit": fields.Int(required=False, load_default=100),
    "user_id": fields.Str(data_key="userId", required=False, load_default="alice")
})
def list_shares(direction="received", status=None, skip=0, limit=100, user_id="alice"):
    """List share invitations."""
    try:
        # Validate status if provided
        status_enum = None
        if status:
            try:
                status_enum = ShareStatus(status)
            except ValueError:
                return jsonify({"error": "Invalid status"}), 400

        svc = current_app.container.share_service

        if direction == "received":
            invites = svc.list_received_invites(user_id, status_enum, skip, limit)
        elif direction == "sent":
            invites = svc.list_sent_invites(user_id, status_enum, skip, limit)
        else:
            return jsonify({"error": "Direction must be 'received' or 'sent'"}), 400

        return jsonify({
            "invites": [invite.model_dump(mode="json") for invite in invites],
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
        if invite.sender_user_id != user_id and invite.recipient_user_id != user_id:
            return jsonify({"error": "Not authorized to view this invitation"}), 403

        return jsonify(invite.model_dump(mode="json")), 200

    except KeyError:
        return jsonify({"error": "Share invitation not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
