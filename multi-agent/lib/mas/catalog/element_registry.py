import threading
from typing import Dict, List, Type
from global_utils.utils.singleton import SingletonMeta
from mas.elements.common.base_element_spec import BaseElementSpec, BaseFactory
from mas.core.enums import ResourceCategory


class ElementRegistry(metaclass=SingletonMeta):
    """
    A registry of all BaseElementSpec classes, keyed by category and type_key.
    Uses a singleton pattern for global access and a reentrant lock for thread safety.
    """
    _lock = threading.RLock()

    def __init__(self) -> None:
        # Map each ResourceCategory to a dict of type_key -> spec class
        self._specs: Dict[ResourceCategory, Dict[str, Type[BaseElementSpec]]] = {}

    # ------------------------------------------------------------------ #
    #  Registration & Access Public API
    # ------------------------------------------------------------------ #
    def register_spec_class(self, spec_cls: Type[BaseElementSpec]) -> None:
        """Register a new BaseElementSpec subclass."""
        with self._lock:
            categories_map = self._specs.setdefault(spec_cls.category, {})
            if spec_cls.type_key in categories_map:
                raise ValueError(
                    f"Spec already registered: {spec_cls.category}/{spec_cls.type_key}"
                )
            categories_map[spec_cls.type_key] = spec_cls

    def get_spec(
            self, category: ResourceCategory, type_key: str
    ) -> Type[BaseElementSpec]:
        """Retrieve the spec class for a given category and type_key."""
        try:
            return self._specs[category][type_key]
        except KeyError:
            raise KeyError(f"No spec registered for {category}/{type_key}")

    def has_spec(self, category: ResourceCategory, type_key: str) -> bool:
        """Returns True if a spec class is registered for the given category and type_key."""
        return type_key in self._specs.get(category, {})

    def get_categories_map(self) -> Dict[ResourceCategory, Dict[str, Type[BaseElementSpec]]]:
        """Return the internal mapping of categories to specs."""
        return self._specs

    def get_category_types_map(self) -> Dict[str, List[str]]:
        """
        Return a mapping of category names to their available type keys.

        Returns:
            Dict mapping category enum values (e.g., "LLMS", "NODES") to lists of type keys
            Example: {"LLMS": ["openai_llm", "mock_llm"], "NODES": ["custom_agent_node", ...]}
        """
        with self._lock:
            result = {}
            for category, types_map in self._specs.items():
                # Get the enum value (e.g., "LLMS" instead of ResourceCategory.LLMS)
                category_name = category.value if hasattr(category, 'value') else str(category)
                # Get all type keys for this category
                type_keys = list(types_map.keys())
                result[category_name] = type_keys
            return result

    def list_categories(self) -> List[ResourceCategory]:
        """List all registered ResourceCategory values."""
        return list(self._specs.keys())

    def list_types(self, category: ResourceCategory) -> List[str]:
        """List all registered type_keys for a given category."""
        return list(self._specs.get(category, {}).keys())

    def get_schema_json(self, category: ResourceCategory, type_key: str) -> dict:
        """Return the JSON schema of the config_model for the spec class."""
        spec_cls = self.get_spec(category, type_key)
        return spec_cls.config_schema.model_json_schema()

    def get_schema(
            self, category: ResourceCategory, type_key: str
    ) -> Type:
        """Return the Pydantic model class (config_schema) for the spec."""
        spec_cls = self.get_spec(category, type_key)
        return spec_cls.config_schema

    def get_factory_class(
            self, category: ResourceCategory, type_key: str
    ) -> Type[BaseFactory]:
        """Return the factory class associated with the spec."""
        spec_cls = self.get_spec(category, type_key)
        return spec_cls.factory_cls

    # ------------------------------------------------------------------ #
    #  Auto-discovery
    # ------------------------------------------------------------------ #
    def auto_discover(self) -> None:
        """
        Discover all BaseElementSpec subclasses on the filesystem (or entry-points)
        and register them as classes (not instances).
        """
        from mas.catalog.spec_discoverer import SpecDiscoverer

        discoverer = SpecDiscoverer()
        for spec_cls in discoverer.discover():
            self.register_spec_class(spec_cls)
