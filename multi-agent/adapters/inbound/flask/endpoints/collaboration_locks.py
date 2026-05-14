"""
Flask collaboration endpoints for team-scoped workspace edit locks.
"""
import logging

from flask import Blueprint, jsonify
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields

from inbound.flask.collaboration_helpers import (
    _acting_user_id,
    holder_to_json,
    internal_error,
    service_for_team,
    service_for_user_team,
    validate_edit_lock_kind,
)

logger = logging.getLogger(__name__)

collaboration_locks_bp = Blueprint("collaboration_locks", __name__)


@collaboration_locks_bp.route("/edit_lock.acquire", methods=["POST"])
@from_body(
    {
        "team_id": fields.Str(data_key="teamId", required=True),
        "entity_kind": fields.Str(data_key="entityKind", required=True),
        "entity_id": fields.Str(data_key="entityId", required=True),
        "display_name": fields.Str(data_key="displayName", load_default=""),
    }
)
def edit_lock_acquire(team_id, entity_kind, entity_id, display_name):
    user_id = _acting_user_id()
    svc, err = service_for_user_team(user_id, team_id)
    if err:
        return err
    kind_err = validate_edit_lock_kind(entity_kind)
    if kind_err:
        return kind_err
    try:
        acquired, holder = svc.acquire_team_edit_lock(
            team_id=team_id,
            entity_kind=entity_kind,
            entity_id=entity_id,
            user_id=user_id,
            display_name=display_name,
        )
        body = {"acquired": acquired}
        if not acquired and holder is not None:
            body["lockedBy"] = holder_to_json(holder)
        return jsonify(body), 200
    except Exception:
        return internal_error(logger, "edit_lock_acquire")


@collaboration_locks_bp.route("/edit_lock.release", methods=["POST"])
@from_body(
    {
        "team_id": fields.Str(data_key="teamId", required=True),
        "entity_kind": fields.Str(data_key="entityKind", required=True),
        "entity_id": fields.Str(data_key="entityId", required=True),
    }
)
def edit_lock_release(team_id, entity_kind, entity_id):
    user_id = _acting_user_id()
    svc, err = service_for_user_team(user_id, team_id)
    if err:
        return err
    kind_err = validate_edit_lock_kind(entity_kind)
    if kind_err:
        return kind_err
    try:
        svc.release_team_edit_lock(team_id, entity_kind, entity_id, user_id)
        return jsonify({"success": True}), 200
    except Exception:
        return internal_error(logger, "edit_lock_release")


@collaboration_locks_bp.route("/edit_lock.heartbeat", methods=["POST"])
@from_body(
    {
        "team_id": fields.Str(data_key="teamId", required=True),
        "entity_kind": fields.Str(data_key="entityKind", required=True),
        "entity_id": fields.Str(data_key="entityId", required=True),
        "display_name": fields.Str(data_key="displayName", load_default=""),
    }
)
def edit_lock_heartbeat(team_id, entity_kind, entity_id, display_name):
    user_id = _acting_user_id()
    svc, err = service_for_user_team(user_id, team_id)
    if err:
        return err
    kind_err = validate_edit_lock_kind(entity_kind)
    if kind_err:
        return kind_err
    try:
        renewed = svc.renew_team_edit_lock(
            team_id, entity_kind, entity_id, user_id, display_name
        )
        return jsonify({"renewed": renewed}), 200
    except Exception:
        return internal_error(logger, "edit_lock_heartbeat")


@collaboration_locks_bp.route("/edit_lock.status", methods=["GET"])
@from_query(
    {
        "team_id": fields.Str(data_key="teamId", required=True),
        "entity_kind": fields.Str(data_key="entityKind", required=True),
        "entity_id": fields.Str(data_key="entityId", required=True),
    }
)
def edit_lock_status(team_id, entity_kind, entity_id):
    svc, err = service_for_team(team_id)
    if err:
        return err
    kind_err = validate_edit_lock_kind(entity_kind)
    if kind_err:
        return kind_err
    try:
        holder = svc.get_team_edit_lock(team_id, entity_kind, entity_id)
        return jsonify({"locked": holder is not None, "lockedBy": holder_to_json(holder)}), 200
    except Exception:
        return internal_error(logger, "edit_lock_status")


@collaboration_locks_bp.route("/edit_lock.statuses", methods=["POST"])
@from_body(
    {
        "team_id": fields.Str(data_key="teamId", required=True),
        "entity_kind": fields.Str(data_key="entityKind", required=True),
        "entity_ids": fields.List(fields.Str(), data_key="entityIds", required=True),
    }
)
def edit_lock_statuses(team_id, entity_kind, entity_ids):
    svc, err = service_for_team(team_id)
    if err:
        return err
    kind_err = validate_edit_lock_kind(entity_kind)
    if kind_err:
        return kind_err
    try:
        batch = svc.get_team_edit_locks_batch(team_id, entity_kind, entity_ids)
        locks = {
            entity_id: holder_to_json(holder) if holder is not None else None
            for entity_id, holder in batch.items()
        }
        return jsonify({"locks": locks}), 200
    except Exception:
        return internal_error(logger, "edit_lock_statuses")
