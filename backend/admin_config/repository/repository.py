"""
Abstract admin config repository interface.

Defines the contract for admin config persistence.
Following the Repository Pattern (DIP — Dependency Inversion Principle).
"""
from abc import ABC, abstractmethod
from typing import Optional

from admin_config.models import AdminConfigEntry


class AdminConfigRepository(ABC):
    """
    Abstract interface for admin config storage.

    Each entry is keyed by a section key (e.g. "slack_channel_restrictions")
    and holds an arbitrary dict of values plus a timestamp.
    """

    @abstractmethod
    def get(self, key: str) -> Optional[AdminConfigEntry]:
        """
        Load a config entry by section key.

        Returns None if no entry exists for the given key.
        """

    @abstractmethod
    def set(self, entry: AdminConfigEntry) -> bool:
        """
        Upsert a config entry.

        Creates the entry if it doesn't exist, updates it otherwise.
        Returns True if the operation succeeded.
        """
