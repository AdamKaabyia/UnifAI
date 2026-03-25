import json
from .base_blueprint_loader import BaseBlueprintLoader
from mas.elements.common.exceptions import InvalidBlueprintError


class JSONBlueprintLoader(BaseBlueprintLoader):
    """
    Loads a JSON blueprint and validates against BlueprintSpec.
    """

    def load(self, path: str) -> BlueprintSpec:
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            raise InvalidBlueprintError(f"Failed to load JSON: {e}")

        try:
            return BlueprintSpec.parse_obj(raw)
        except Exception as e:
            raise InvalidBlueprintError(f"Invalid blueprint format: {e}")
