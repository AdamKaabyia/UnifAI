"""Abstract team repository interface."""
from abc import ABC, abstractmethod
from typing import List, Optional

from teams.models import Team


class TeamRepository(ABC):

    @abstractmethod
    def create(self, doc: Team) -> str:
        """Persist a new team. Returns the team_id."""

    @abstractmethod
    def get(self, team_id: str) -> Team:
        """Retrieve a team by ID. Raises KeyError if not found."""

    @abstractmethod
    def find_by_member(self, member_id: str) -> List[Team]:
        """Return all teams that include *member_id* in their members list."""

    @abstractmethod
    def find_by_name(self, name: str) -> Optional[Team]:
        """Return the team with the given name, or None."""

    @abstractmethod
    def update(self, doc: Team) -> str:
        """Replace an existing team. Raises KeyError if not found."""

    @abstractmethod
    def delete(self, team_id: str) -> None:
        """Delete a team by ID. Raises KeyError if not found."""
