from datetime import datetime
from typing import List, Optional

from teams.models import Team, DirectoryUser
from teams.repository.repository import TeamRepository
from teams.providers.provider import TeamDirectoryProvider


class TeamService:
    def __init__(
        self,
        repository: TeamRepository,
        directory_provider: Optional[TeamDirectoryProvider] = None,
    ):
        self._repo = repository
        self._directory = directory_provider

    # ────────────────────── local team CRUD ───────────────────────────

    def create(self, name: str, created_by: str, members: List[str]) -> Team:
        if self._repo.find_by_name(name):
            raise ValueError(f"Team with name '{name}' already exists")

        if created_by not in members:
            members = [created_by] + members

        team = Team(
            name=name,
            created_by=created_by,
            members=members,
        )
        self._repo.create(team)
        return team

    def get(self, team_id: str) -> Team:
        return self._repo.get(team_id)

    def list_user_teams(self, user_id: str) -> List[Team]:
        return self._repo.find_by_member(user_id)

    def update(self, team_id: str, name: Optional[str] = None,
               members: Optional[List[str]] = None) -> Team:
        team = self._repo.get(team_id)

        if name and name != team.name:
            existing = self._repo.find_by_name(name)
            if existing:
                raise ValueError(f"Team with name '{name}' already exists")
            team.name = name

        if members is not None:
            if team.created_by not in members:
                members = [team.created_by] + members
            team.members = members

        team.updated_at = datetime.utcnow()
        self._repo.update(team)
        return team

    def delete(self, team_id: str) -> None:
        self._repo.delete(team_id)

    # ────────────────────── directory lookups ─────────────────────────

    @property
    def has_directory(self) -> bool:
        return self._directory is not None

    def _apply_user_token(self, user_token: Optional[str] = None) -> None:
        if user_token and self._directory:
            self._directory.set_user_token(user_token)

    def search_directory_users(self, query: str, limit: int = 20,
                               user_token: Optional[str] = None) -> List[DirectoryUser]:
        if not self._directory:
            return []
        self._apply_user_token(user_token)
        return self._directory.search_users(query, limit=limit)

    def get_directory_user(self, user_id: str,
                           user_token: Optional[str] = None) -> Optional[DirectoryUser]:
        if not self._directory:
            return None
        self._apply_user_token(user_token)
        return self._directory.get_user(user_id)
