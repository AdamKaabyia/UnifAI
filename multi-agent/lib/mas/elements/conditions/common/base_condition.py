from abc import ABC, abstractmethod
from typing import Any, Optional, ClassVar

from mas.graph.models import StepContext
from mas.graph.state.graph_state import GraphState
from mas.graph.state.state_view import StateView
from .models import ConditionOutputSchema


class BaseCondition(ABC):
    """
    Base condition with StateView support and output schema.
    
    • Provides __call__ with StateView wrapping
    • Delegates to run() method that works with StateView
    • Conditions read state and return branch selector values
    """
    READS: ClassVar[set[str]] = set()
    # Conditions typically don't write to state, but keeping for consistency
    WRITES: ClassVar[set[str]] = set()

    def __init__(self, *args, **kwargs):
        # In case subclasses override __init__, they *must* call super().__init__()
        # to ensure _ctx is defined. This is explicit and avoids the implicit
        # class-attribute fallback.
        super().__init__()
        self._ctx: Optional[StepContext] = None

    def __call__(self, state: GraphState, config=None) -> Any:
        """
        Wrap GraphState with StateView and delegate to run method.
        Returns the branch selector key.
        """
        # Wrap state with StateView for read/write permission enforcement
        wrapped_state = StateView(state, reads=self.read_channels(), writes=self.write_channels())
        
        # Delegate to run method that works with StateView
        return self.run(wrapped_state)

    @abstractmethod
    def run(self, state: StateView) -> Any:
        """
        Evaluate the condition against the provided StateView and
        return the branch selector key.
        
        Subclasses implement this method instead of __call__.
        """
        ...

    def set_context(self, step_ctx: StepContext) -> None:
        """Inject the `StepContext` built by the runtime layer."""
        self._ctx = step_ctx

    @classmethod
    def read_channels(cls) -> set[str]:
        return cls.READS

    @classmethod
    def write_channels(cls) -> set[str]:
        return cls.WRITES

    # Convenience accessor
    @property
    def context(self) -> Optional[StepContext]:
        return self._ctx

    @classmethod
    def get_output_schema(cls) -> ConditionOutputSchema:
        """
        Define what outputs this condition can produce.
        Used by UI to know what branches to allow.
        
        MUST be implemented by all condition subclasses.
        """
        raise NotImplementedError(f"{cls.__name__} must implement get_output_schema() class method")
