from datetime import datetime
from enum import Enum
from typing import List
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class TeamMemberType(str, Enum):
    USER = "user"
    GROUP = "group"


class TeamMember(BaseModel):
    """A member entry in a team — either an individual user or an LDAP group."""
    type: TeamMemberType
    id: str
    display_name: str = ""


class Team(BaseModel):
    team_id: str = Field(default_factory=lambda: uuid4().hex)
    name: str
    created_by: str
    members: List[TeamMember] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="before")
    @classmethod
    def _normalize_members(cls, data):
        """Handle legacy documents that store members as plain strings."""
        if isinstance(data, dict) and "members" in data:
            normalized = []
            for item in data["members"]:
                if isinstance(item, str):
                    normalized.append({"type": "user", "id": item, "display_name": item})
                else:
                    normalized.append(item)
            data["members"] = normalized
        return data
