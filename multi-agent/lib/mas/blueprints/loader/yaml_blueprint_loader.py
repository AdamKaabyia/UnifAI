from pydantic import ValidationError
import yaml
from .base_blueprint_loader import BaseBlueprintLoader
from mas.blueprints.models.blueprint import BlueprintSpec
from .exceptions import InvalidBlueprintError


class YAMLBlueprintLoader(BaseBlueprintLoader):
    def load(self, path: str):
        try:
            raw = yaml.safe_load(open(path, "r", encoding="utf-8"))
        except Exception as e:
            raise InvalidBlueprintError(f"YAML load failed: {e}")

        # try:
            # spec = BlueprintSpec.parse_obj(raw)
        # except ValidationError as e:
        #     raise InvalidBlueprintError(f"Blueprint validation error:\n{e}")
        return raw
