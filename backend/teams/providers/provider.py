"""
Abstract user-directory provider interface.

Defines the contract for any external system that owns user identity
data (corporate LDAP, SSO user-store, etc.).

Domain code depends only on this port.  Concrete adapters live under
providers/<backend_name>/ and are selected in the composition root
(app_container), so the rest of the application never knows which
directory service is behind the abstraction.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from teams.models import DirectoryUser


class TeamDirectoryProvider(ABC):
    """Port for an external user directory."""

    def set_user_token(self, token: str) -> None:
        """Supply the calling user's access token for providers that
        authenticate on behalf of the logged-in user rather than using
        service-level credentials.  Default implementation is a no-op;
        adapters that need it override this."""

    @abstractmethod
    def search_users(self, query: str, limit: int = 20) -> List[DirectoryUser]:
        """Free-text search over the directory's user base.

        Implementations should match on username, display name, e-mail, etc.
        """

    @abstractmethod
    def get_user(self, user_id: str) -> Optional[DirectoryUser]:
        """Look up a single user by their unique directory identifier."""
