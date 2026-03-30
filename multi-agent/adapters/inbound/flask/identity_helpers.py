"""
Helpers for resolving an Identity from Flask request parameters.

Backward-compatible: when only ``userId`` is supplied (no ``identityType``),
the identity defaults to ``IdentityType.USER``.
"""
from mas.core.identity import Identity, IdentityType

_TYPE_MAP = {
    "user": IdentityType.USER,
    "team": IdentityType.TEAM,
}


def resolve_identity(
    user_id: str,
    identity_type: str = "user",
    display_name: str = "",
) -> Identity:
    """Build an ``Identity`` from raw request parameters."""
    id_type = _TYPE_MAP.get(identity_type, IdentityType.USER)
    if id_type == IdentityType.TEAM:
        return Identity.team(team_id=user_id, display_name=display_name)
    return Identity.user(user_id=user_id, display_name=display_name)
