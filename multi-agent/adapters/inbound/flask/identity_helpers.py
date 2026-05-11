"""
Helpers for resolving an Identity from raw request parameters.

``resolve_identity`` is the low-level builder: it turns raw strings
(``userId``, ``identityType``) into an ``Identity`` domain object.

For endpoint-level usage prefer the ``@with_identity`` decorator in
``inbound.flask.decorators`` — it reads the params from the Flask request
automatically and injects the resolved ``Identity`` as a kwarg.
"""
from __future__ import annotations

from global_utils.identity import Identity, IdentityType

_TYPE_MAP = {
    "user": IdentityType.USER,
    "team": IdentityType.TEAM,
}

_VALID_TYPES = frozenset(_TYPE_MAP.keys())


def authenticated_username() -> str:
    """Username from the auth gateway (trusted). Empty if unset (e.g. local dev)."""
    from flask import has_request_context, request

    if not has_request_context():
        return ""
    return (request.headers.get("X-Authenticated-User") or "").strip()


def resolve_identity(
    user_id: str,
    identity_type: str = "user",
    display_name: str = "",
) -> Identity:
    """Build an ``Identity`` from raw request parameters.

    Raises ``ValueError`` if *identity_type* is not a recognized value.
    """
    if identity_type not in _VALID_TYPES:
        raise ValueError(
            f"Invalid identityType '{identity_type}'; "
            f"must be one of {sorted(_VALID_TYPES)}"
        )
    id_type = _TYPE_MAP[identity_type]
    if id_type == IdentityType.TEAM:
        return Identity.team(team_id=user_id, display_name=display_name)
    return Identity.user(user_id=user_id, display_name=display_name)
