"""
Graph traversal algorithm — Pregel / Bulk Synchronous Parallel (BSP).

Each superstep proceeds in three phases:

  PLAN    — Determine which nodes are ready to run. If none remain the
            graph is complete. If the step counter exceeds the recursion
            limit, raise GraphRecursionError.
  EXECUTE — Run all planned nodes in parallel against the *same* state
            snapshot (write isolation within a superstep).
  UPDATE  — Route every node output through channels (extract writes,
            apply merge strategies via channel.update), track which
            channels actually changed, advance the step counter.

All writes — including single-node supersteps — flow through channels,
ensuring merge strategies are always respected.

Edge-driven scheduling: successor resolution uses explicit graph edges
and conditional edges, combined with a predecessor gate (a node becomes
active only when *all* its predecessors have executed).

Uses callbacks for node execution and condition evaluation so that the
infrastructure layer can supply its own implementations (e.g., Temporal
activities) while reusing the traversal logic.
"""
import asyncio
from typing import Any, Dict, List, Optional, Set, Tuple, Type

from mas.engine.domain.errors import GraphRecursionError
from mas.engine.domain.models import GraphDefinition
from mas.engine.domain.types import (
    DEFAULT_RECURSION_LIMIT,
    EvaluateConditionFn,
    ExecuteNodeFn,
    OnSuperstepFn,
)
from mas.graph.state.channel_types import _MISSING, build_channel_registry
from mas.graph.state.graph_state import GraphState


class GraphTraversal:
    """
    Core graph traversal using the BSP superstep model with edge-driven
    scheduling and channel-based state reconciliation.
    """

    def __init__(
        self,
        graph_def: GraphDefinition,
        state_cls: Type[GraphState] = GraphState,
        recursion_limit: int = DEFAULT_RECURSION_LIMIT,
    ) -> None:
        self._graph = graph_def
        self._state_cls = state_cls
        self._predecessors = graph_def.get_predecessors()
        self._channels = build_channel_registry(state_cls)
        self._recursion_limit = recursion_limit

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    async def run(
        self,
        initial_state: GraphState,
        execute_node: ExecuteNodeFn,
        evaluate_condition: EvaluateConditionFn,
        on_superstep: Optional[OnSuperstepFn] = None,
    ) -> GraphState:
        state = initial_state
        executed: Set[str] = set()
        active: Set[str] = {self._graph.entry}
        step = 0

        while True:
            # ── PLAN ──────────────────────────────────────
            if not active:
                break

            if step >= self._recursion_limit:
                raise GraphRecursionError(self._recursion_limit)

            if on_superstep:
                on_superstep(step, active, state)

            # ── EXECUTE ───────────────────────────────────
            results = await self._execute_superstep(active, state, execute_node)

            # ── UPDATE ────────────────────────────────────
            state, updated_channels = self._apply_writes(state, results)
            executed.update(active)
            step += 1

            # Resolve next active set (edge-driven)
            active = await self._next_active(
                active, executed, state, evaluate_condition,
            )

        return state

    # ------------------------------------------------------------------ #
    #  EXECUTE phase
    # ------------------------------------------------------------------ #

    async def _execute_superstep(
        self,
        uids: Set[str],
        state: GraphState,
        execute_node: ExecuteNodeFn,
    ) -> List[GraphState]:
        if len(uids) == 1:
            uid = next(iter(uids))
            return [await execute_node(uid, state, self._graph)]

        tasks = [
            execute_node(uid, state, self._graph)
            for uid in sorted(uids)
        ]
        return list(await asyncio.gather(*tasks))

    # ------------------------------------------------------------------ #
    #  UPDATE phase — channel-based apply_writes
    # ------------------------------------------------------------------ #

    def _apply_writes(
        self,
        original: GraphState,
        results: List[GraphState],
    ) -> Tuple[GraphState, Set[str]]:
        """
        Route all node outputs through channels, mirroring LangGraph's
        apply_writes() from _algo.py.

        For each channel (GraphState field):
          1. extract_write — infer what each node wrote
          2. group writes  — collect non-MISSING writes
          3. channel.update — reconcile via merge strategy

        Returns (new_state, updated_channels).
        """
        updated_channels: Set[str] = set()
        accumulated: Dict[str, Any] = {}

        for field_name, channel in self._channels.items():
            base_value = getattr(original, field_name)

            writes: List[Any] = []
            for result in results:
                write = channel.extract_write(
                    base_value, getattr(result, field_name),
                )
                if write is not _MISSING:
                    writes.append(write)

            if writes:
                new_value = channel.update(base_value, writes)
                accumulated[field_name] = new_value
                if new_value != base_value:
                    updated_channels.add(field_name)
            else:
                accumulated[field_name] = base_value

        return self._state_cls(**accumulated), updated_channels

    # ------------------------------------------------------------------ #
    #  Edge-driven successor resolution
    # ------------------------------------------------------------------ #

    async def _next_active(
        self,
        current: Set[str],
        executed: Set[str],
        state: GraphState,
        evaluate_condition: EvaluateConditionFn,
    ) -> Set[str]:
        """Resolve successors and gate on predecessors."""
        candidates: Set[str] = set()
        for uid in current:
            candidates.update(
                await self._resolve_successors(uid, state, evaluate_condition),
            )

        return {
            uid for uid in candidates
            if all(
                dep in executed
                for dep in self._predecessors.get(uid, set())
            )
        }

    async def _resolve_successors(
        self,
        uid: str,
        state: GraphState,
        evaluate_condition: EvaluateConditionFn,
    ) -> Set[str]:
        successors: Set[str] = set()

        if uid in self._graph.conditional_edges:
            cond = self._graph.conditional_edges[uid]
            outcome = await evaluate_condition(state, cond)

            if isinstance(outcome, str):
                chosen = cond.branches.get(outcome)
                if chosen:
                    successors.add(chosen)
            elif isinstance(outcome, (list, tuple)):
                for target in outcome:
                    chosen = cond.branches.get(target)
                    if chosen:
                        successors.add(chosen)

        elif uid in self._graph.edges:
            successors.update(self._graph.edges[uid])

        return successors
