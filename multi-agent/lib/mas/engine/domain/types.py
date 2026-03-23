"""
Callback protocols and constants for the graph traversal engine.

These define the contracts between the traversal algorithm and the
execution layer (Temporal, LangGraph, or any future engine).
"""
from typing import Any, Protocol, Set

from mas.engine.domain.models import ConditionalEdgeDef, GraphDefinition
from mas.graph.state.graph_state import GraphState

DEFAULT_RECURSION_LIMIT = 25


class ExecuteNodeFn(Protocol):
    """Execute a single graph node and return the updated state."""

    async def __call__(
        self,
        uid: str,
        state: GraphState,
        graph_def: GraphDefinition,
    ) -> GraphState: ...


class EvaluateConditionFn(Protocol):
    """Evaluate a conditional edge and return the routing outcome."""

    async def __call__(
        self,
        state: GraphState,
        condition: ConditionalEdgeDef,
    ) -> Any: ...


class OnSuperstepFn(Protocol):
    """Called at the start of each superstep for observability."""

    def __call__(
        self,
        step: int,
        active_nodes: Set[str],
        state: GraphState,
    ) -> None: ...
