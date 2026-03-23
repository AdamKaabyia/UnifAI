from typing import Protocol, runtime_checkable, Mapping, Any, Iterator, TYPE_CHECKING

if TYPE_CHECKING:
    from mas.graph.state.state_view import StateView
    from mas.graph.models import StepContext
from abc import ABC, abstractmethod
from .enums import ResourceCategory


@runtime_checkable
class SupportsStreaming(Protocol):
    def _stream(self, payload: Mapping[str, Any]) -> None: ...

    def is_streaming(self) -> bool: ...


@runtime_checkable  
class SupportsStateContext(Protocol):
    """
    Protocol for classes that provide access to graph state and step context.
    
    This ensures that mixins requiring state/context access can only be used
    with classes that provide these capabilities.
    """
    def get_state(self) -> "StateView":
        """Get the current state view for this node."""
        ...
    
    def get_context(self) -> "StepContext":
        """Get the current step context for this node."""
        ...


class LLMSupportsStreaming(ABC):
    @abstractmethod
    def stream(self, messages: list[Any], **kwargs) -> Iterator[str]:
        """
        Yields each token (or chunk) as it arrives.
        """
        ...


class SessionRegistry(Protocol):
    def register(self, category: ResourceCategory, rid: str, 
                instance: Any, config: Any, spec: Any) -> None: ...

    def get(self, category: ResourceCategory, rid: str) -> Any: ...
    
    def get_instance(self, category: ResourceCategory, rid: str) -> Any: ...
    
    def get_config(self, category: ResourceCategory, rid: str) -> Any: ...
    
    def get_spec(self, category: ResourceCategory, rid: str) -> Any: ...

    def get_runtime_element(self, category: ResourceCategory, rid: str) -> Any: ...
