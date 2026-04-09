"""
Lightweight Identity model for the multi-agent service.

Mirrors the canonical definition in sso-backend/identity/models.py
so that this service has no cross-service import dependency.
"""
from enum import Enum

from pydantic import BaseModel


class IdentityType(str, Enum):
    USER = "user"
    TEAM = "team"


class Identity(BaseModel):
    """Lightweight owner reference -- user or team."""
    type: IdentityType
    id: str
    display_name: str = ""
    email: str = ""

    @classmethod
    def user(cls, user_id: str, display_name: str = "",
             email: str = "") -> "Identity":
        return cls(type=IdentityType.USER, id=user_id,
                   display_name=display_name or user_id, email=email)

    @classmethod
    def team(cls, team_id: str, display_name: str = "") -> "Identity":
        return cls(type=IdentityType.TEAM, id=team_id,
                   display_name=display_name or team_id)
