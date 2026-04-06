from datetime import datetime
from typing import List, Optional

from teams.models import Team, TeamMember, TeamMemberType
from teams.repository.repository import TeamRepository


class TeamService:
    def __init__(self, repository: TeamRepository):
        self._repo = repository

    # ────────────────────── local team CRUD ───────────────────────────

    def create(self, name: str, created_by: str,
               members: Optional[List] = None) -> Team:
        if self._repo.find_by_name(name):
            raise ValueError(f"Team with name '{name}' already exists")

        parsed_members = self._parse_members(members or [])

        creator_present = any(
            m.id == created_by and m.type == TeamMemberType.USER
            for m in parsed_members
        )
        if not creator_present:
            parsed_members.insert(
                0, TeamMember(type=TeamMemberType.USER, id=created_by,
                              display_name=created_by),
            )

        team = Team(name=name, created_by=created_by, members=parsed_members)
        self._repo.create(team)
        return team

    def get(self, team_id: str) -> Team:
        return self._repo.get(team_id)

    def list_user_teams(self, user_id: str,
                        group_ids: Optional[List[str]] = None) -> List[Team]:
        return self._repo.find_by_member(user_id, group_ids=group_ids)

    def update(self, team_id: str, name: Optional[str] = None,
               members: Optional[List] = None) -> Team:
        team = self._repo.get(team_id)

        if name and name != team.name:
            existing = self._repo.find_by_name(name)
            if existing:
                raise ValueError(f"Team with name '{name}' already exists")
            team.name = name

        if members is not None:
            parsed = self._parse_members(members)
            creator_present = any(
                m.id == team.created_by and m.type == TeamMemberType.USER
                for m in parsed
            )
            if not creator_present:
                parsed.insert(
                    0, TeamMember(type=TeamMemberType.USER, id=team.created_by,
                                  display_name=team.created_by),
                )
            team.members = parsed

        team.updated_at = datetime.utcnow()
        self._repo.update(team)
        return team

    def delete(self, team_id: str) -> None:
        self._repo.delete(team_id)

    # ── helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_members(raw: List) -> List[TeamMember]:
        """Accept either TeamMember dicts or plain strings (backward compat)."""
        result: List[TeamMember] = []
        for item in raw:
            if isinstance(item, str):
                result.append(TeamMember(type=TeamMemberType.USER, id=item,
                                         display_name=item))
            elif isinstance(item, dict):
                result.append(TeamMember(**item))
            elif isinstance(item, TeamMember):
                result.append(item)
        return result
