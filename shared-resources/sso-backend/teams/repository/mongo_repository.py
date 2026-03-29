from typing import List, Optional

import pymongo
from pymongo.database import Database

from teams.models import Team
from teams.repository.repository import TeamRepository


class MongoTeamRepository(TeamRepository):
    def __init__(self, db: Database, coll_name: str = "teams"):
        self.col = db[coll_name]
        self.col.create_index("name", unique=True)
        self.col.create_index("members.id")

    def create(self, doc: Team) -> str:
        result = self.col.insert_one({
            "_id": doc.team_id,
            **doc.model_dump(mode="json"),
        })
        if not result.acknowledged:
            raise RuntimeError(f"Failed to insert team: {doc.team_id}")
        return doc.team_id

    def get(self, team_id: str) -> Team:
        raw = self.col.find_one({"_id": team_id})
        if not raw:
            raise KeyError(team_id)
        return Team(**raw)

    def find_by_member(self, member_id: str) -> List[Team]:
        cursor = self.col.find({"members.id": member_id}).sort(
            "created_at", pymongo.DESCENDING,
        )
        return [Team(**doc) for doc in cursor]

    def find_by_name(self, name: str) -> Optional[Team]:
        raw = self.col.find_one({"name": name})
        return Team(**raw) if raw else None

    def update(self, doc: Team) -> str:
        result = self.col.replace_one(
            {"_id": doc.team_id},
            doc.model_dump(mode="json"),
        )
        if result.matched_count == 0:
            raise KeyError(f"No team found with id: {doc.team_id}")
        return doc.team_id

    def delete(self, team_id: str) -> None:
        result = self.col.delete_one({"_id": team_id})
        if result.deleted_count == 0:
            raise KeyError(team_id)
