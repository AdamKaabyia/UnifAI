from abc import ABC, abstractmethod
from typing import List, ClassVar, Type
from mas.graph.graph_plan import GraphPlan


class Validator(ABC):
    """Abstract base validator with automatic registration."""
    
    _registry: ClassVar[List[Type["Validator"]]] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._registry.append(cls)

    @classmethod
    def get_all_validators(cls) -> List[Type["Validator"]]:
        return cls._registry.copy()

    @property
    def name(self) -> str:
        return self.__class__.__name__.lower().replace('validator', '')

    @abstractmethod
    def validate(self, plan: GraphPlan) -> "ValidationReport":
        """Validate the graph plan and return a report."""
        pass 