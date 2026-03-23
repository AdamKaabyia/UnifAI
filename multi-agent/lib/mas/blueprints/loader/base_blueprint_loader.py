# blueprints/base_blueprint_loader.py

from abc import ABC, abstractmethod
from typing import Any


# from schemas.blueprint_schema import BlueprintSpec


class BaseBlueprintLoader(ABC):
    """
    Abstract base class for loading user-submitted blueprint files
    (YAML, JSON, etc) and validating them into BlueprintSpec objects.
    """

    @abstractmethod
    def load(self, path: str):
        """
        Load, parse and validate a blueprint file.

        Args:
            path (str): Path to the blueprint file.

        Returns:
            BlueprintSpec: Fully validated in-memory spec.
        """
        raise NotImplementedError
