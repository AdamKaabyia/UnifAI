"""
Outbound adapter for Identity pod team APIs — delegates to IdentityClient.

Preserves the existing public interface (``is_member``, ``resolve_team_id``,
``get_team_ids``, ``configured``) so that inbound adapters (Flask endpoints,
collaboration helpers) keep working unchanged.
"""
import logging
from typing import Optional

from global_utils.identity_client import IdentityClient

logger = logging.getLogger(__name__)


class IdentityTeamsClient:
    """Thin wrapper around :class:`IdentityClient` for the ``teams.*`` APIs.

    Registered in the DI container so that inbound adapters can consume it
    via ``current_app.container`` without making raw HTTP calls.
    """

    def __init__(self, identity_client: IdentityClient):
        self._client = identity_client

    @property
    def configured(self) -> bool:
        """True when an identity base URL has been provided."""
        return self._client.configured

    def get_team_ids(self, username: str) -> frozenset[str]:
        """Return the set of team IDs the *username* belongs to (cached)."""
        return self._client.get_team_ids(username)

    def is_member(self, username: str, team_id: str) -> bool:
        """Return True when *username* is a member of *team_id*.

        Fails open when not configured; fails closed on error.
        """
        return self._client.is_member(username, team_id)

    def resolve_team_id(self, username: str, team_name_or_id: str) -> Optional[str]:
        """Map a team display name or id to its canonical ``team_id``."""
        return self._client.resolve_team_id(username, team_name_or_id)
