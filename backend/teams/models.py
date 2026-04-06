from datetime import datetime
from enum import Enum
from typing import List
from uuid import uuid4
from pydantic import BaseModel, Field, model_validator


class TeamMemberType(str, Enum):
    USER = "user"
    GROUP = "group"


class TeamMember(BaseModel):
    """A member entry in a team — either an individual user or an LDAP/ROVER group."""
    type: TeamMemberType
    id: str
    display_name: str = ""
    group_members: List[str] = Field(default_factory=list)


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

    def effective_member_count(self) -> int:
        """Unique individual users: direct users + users inside groups."""
        ids: set = set()
        for m in self.members:
            if m.type == TeamMemberType.USER:
                ids.add(m.id)
            elif m.type == TeamMemberType.GROUP and m.group_members:
                ids.update(m.group_members)
        return len(ids)
