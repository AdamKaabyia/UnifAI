from typing import Type, Callable, Any, Dict
from langgraph.graph import StateGraph, END
from mas.engine.domain.base_builder import BaseGraphBuilder
from mas.engine.domain.base_executor import BaseGraphExecutor
from mas.graph.state.graph_state import GraphState
from outbound.langgraph.executor import LangGraphExecutor


class LangGraphBuilder(BaseGraphBuilder):
    """
    Concrete GraphBuilder that targets LangGraph's StateGraph API.
    """

    def __init__(self, state_cls: GraphState) -> None:
        self._graph = StateGraph(state_cls)

    def add_node(self, uid: str, func: Any) -> None:
        self._graph.add_node(uid, func)

    def add_edge(self, from_node: str, to_node: str) -> None:
        self._graph.add_edge(from_node, to_node)

    def add_conditional_edge(
            self,
            from_node: str,
            condition: Callable[[Dict[str, Any]], Any],
            branches: Dict[Any, str]
    ) -> None:
        self._graph.add_conditional_edges(
            from_node,
            condition,
            branches
        )

    def set_entry(self, uid: str) -> None:
        self._graph.set_entry_point(uid)

    def set_exit(self, uid: str) -> None:
        self._graph.set_finish_point(uid or END)

    def build_executor(self) -> BaseGraphExecutor:
        return LangGraphExecutor(self._graph.compile())
