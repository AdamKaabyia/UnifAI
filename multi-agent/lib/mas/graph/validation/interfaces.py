from abc import ABC, abstractmethod
from typing import List, ClassVar, Type
from mas.graph.graph_plan import GraphPlan
from .models import ValidationReport
from .fix_models import FixSuggestion


class ValidationProvider(ABC):
    """Interface for components that validate graph plans."""
    
    _registry: ClassVar[List[Type["ValidationProvider"]]] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._registry.append(cls)

    @classmethod
    def get_all_providers(cls) -> List[Type["ValidationProvider"]]:
        return cls._registry.copy()

    @property
    def name(self) -> str:
        return self.__class__.__name__.lower().replace('validator', '').replace('provider', '')

    @abstractmethod
    def validate(self, plan: GraphPlan) -> ValidationReport:
        """Validate the graph plan and return a report."""
        pass


class FixSuggestionProvider(ABC):
    """Interface for components that suggest fixes for validation issues."""
    
    _registry: ClassVar[List[Type["FixSuggestionProvider"]]] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._registry.append(cls)

    @classmethod
    def get_all_providers(cls) -> List[Type["FixSuggestionProvider"]]:
        return cls._registry.copy()

    @property
    def name(self) -> str:
        return self.__class__.__name__.lower().replace('suggester', '').replace('provider', '').replace('fix', '')

    @abstractmethod
    def suggest_fixes(
        self, 
        plan: GraphPlan, 
        validation_report: ValidationReport | None = None
    ) -> List[FixSuggestion]:
        """Suggest fixes for the graph plan, optionally using validation results."""
        pass