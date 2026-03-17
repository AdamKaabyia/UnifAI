from abc import ABC, abstractmethod
from typing import Any
from mas.graph.state.graph_state import GraphState


class BaseGraphExecutor(ABC):
    """
    Abstract base class for graph executors.

    Streaming is NOT this class's concern — it is handled orthogonally
    by the channel layer (SessionChannel / SessionChannelReader).
    Executors only know how to run a graph to completion.
    """

    @abstractmethod
    def run(self, initial_state: GraphState, *, session_id: str = "") -> GraphState:
        """
        Drive the graph from its entry to its exit and return the final state.

        Args:
            initial_state: The starting graph state.
            session_id: Optional session identifier used by distributed
                        executors to enable channel-based streaming on workers.
        """
        ...

    @abstractmethod
    def get_state(self) -> Any:
        """
        Get the current state of the graph.
        """
        ...
