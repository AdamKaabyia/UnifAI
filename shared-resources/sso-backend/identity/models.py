"""
Platform-wide Identity model.

An Identity is the minimal, portable reference to "who owns this thing".
It can represent either a single user or a team.  All services should use
this model instead of raw ``user_id`` strings.
"""
from enum import Enum

from pydantic import BaseModel


class IdentityType(str, Enum):
    USER = "user"
    TEAM = "team"


class Identity(BaseModel):
    """Lightweight owner reference -- user or team.

    Carries enough metadata so that consuming services can display
    the owner without a round-trip to the directory.
    """
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
