from typing import List

from pydantic import BaseModel, Field


class DirectoryUser(BaseModel):
    """A user record from an external directory (e.g. LDAP, SSO user-store)."""
    user_id: str
    username: str
    display_name: str
    email: str = ""
    title: str = ""


class DirectoryGroup(BaseModel):
    """A group record from an external directory (e.g. LDAP ou=groups)."""
    group_id: str
    name: str
    description: str = ""
    members: List[str] = Field(default_factory=list)
