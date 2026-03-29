from datetime import datetime
from typing import List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from global_utils.directory.models import DirectoryUser


class Team(BaseModel):
    team_id: str = Field(default_factory=lambda: uuid4().hex)
    name: str
    created_by: str
    members: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


__all__ = ["Team", "DirectoryUser"]
