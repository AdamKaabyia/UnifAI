from datetime import datetime
from typing import List, Optional

from directory.models import DirectoryUser, DirectoryGroup
from directory.provider import DirectoryProvider
from teams.models import Team, TeamMember, TeamMemberType
from teams.repository.repository import TeamRepository


class TeamService:
    def __init__(
        self,
        repository: TeamRepository,
        directory_provider: Optional[DirectoryProvider] = None,
    ):
        self._repo = repository
        self._directory = directory_provider

    # ── team CRUD ──────────────────────────────────────────────────────

    def create(self, name: str, created_by: str,
               members: Optional[List[dict]] = None) -> Team:
        if self._repo.find_by_name(name):
            raise ValueError(f"Team with name '{name}' already exists")

        parsed_members = self._parse_members(members or [])

        creator_present = any(
            m.id == created_by and m.type == TeamMemberType.USER
            for m in parsed_members
        )
        if not creator_present:
            parsed_members.insert(
                0, TeamMember(type=TeamMemberType.USER, id=created_by, display_name=created_by),
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
               members: Optional[List[dict]] = None) -> Team:
        team = self._repo.get(team_id)

        if name and name != team.name:
            if self._repo.find_by_name(name):
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

    # ── directory lookups ──────────────────────────────────────────────

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

    def search_directory_groups(self, query: str, limit: int = 20,
                                user_token: Optional[str] = None) -> List[DirectoryGroup]:
        if not self._directory:
            return []
        self._apply_user_token(user_token)
        return self._directory.search_groups(query, limit=limit)

    def get_directory_group(self, group_id: str,
                            user_token: Optional[str] = None) -> Optional[DirectoryGroup]:
        if not self._directory:
            return None
        self._apply_user_token(user_token)
        return self._directory.get_group(group_id)

    def get_user_groups(self, user_id: str,
                        user_token: Optional[str] = None) -> List[DirectoryGroup]:
        if not self._directory:
            return []
        self._apply_user_token(user_token)
        return self._directory.get_user_groups(user_id)

    # ── group-member sync ────────────────────────────────────────────

    def refresh_group_members(self, groups: List[dict]) -> None:
        """Update ``group_members`` on every team that references any of
        the given groups.  *groups* is a list of directory-group dicts,
        each containing at least ``group_id`` and ``members``."""
        for g in groups:
            group_id = g.get("group_id")
            members = g.get("members")
            if group_id and members is not None:
                self._repo.update_group_members(group_id, members)

    # ── helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_members(raw: List[dict]) -> List[TeamMember]:
        """Accept either TeamMember dicts or plain strings (backward compat)."""
        result: List[TeamMember] = []
        for item in raw:
            if isinstance(item, str):
                result.append(TeamMember(type=TeamMemberType.USER, id=item, display_name=item))
            elif isinstance(item, dict):
                result.append(TeamMember(**item))
            elif isinstance(item, TeamMember):
                result.append(item)
        return result
