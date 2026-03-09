from datetime import datetime
from typing import List
from uuid import uuid4
from pydantic import BaseModel, Field


class Team(BaseModel):
    team_id: str = Field(default_factory=lambda: uuid4().hex)
    name: str
    created_by: str
    members: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
