"""
Engine domain models for graph topology.

GraphDefinition is a fully serializable representation of a graph's
structure (nodes, edges, conditional routing).  It carries NO callables —
only string identifiers (uid, rid) that are resolved at execution time.

Used by any engine that needs to describe a graph across process
boundaries (e.g., distributed workers, durable workflows).
"""
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field

from mas.graph.models.step_context import StepContext


class NodeDef(BaseModel):
    """
    Identity and deployment info for a single graph node.

    Carries the mini-blueprint and step context so that a remote
    worker can rebuild this specific node without loading the full
    blueprint from a database.
    """
    uid: str
    rid: str
    node_blueprint: Dict[str, Any] = Field(default_factory=dict)
    step_context: Optional[StepContext] = None

    model_config = ConfigDict(frozen=True)


class ConditionalEdgeDef(BaseModel):
    """A conditional routing rule attached to a node."""
    condition_rid: str
    condition_blueprint: Dict[str, Any] = Field(default_factory=dict)
    step_context: Optional[StepContext] = None
    branches: Dict[str, str] = Field(
        default_factory=dict,
    )

    model_config = ConfigDict(frozen=True)


class GraphDefinition(BaseModel):
    """
    Serializable graph topology.

    Contains only data (uids, rids, edges).  The workflow uses this
    for traversal decisions (which node next, which branch to take).
    Callables live separately in the activity layer.
    """
    nodes: Dict[str, NodeDef] = Field(default_factory=dict)
    edges: Dict[str, List[str]] = Field(default_factory=dict)
    conditional_edges: Dict[str, ConditionalEdgeDef] = Field(default_factory=dict)
    entry: str = ""
    exit_node: str = ""

    model_config = ConfigDict(frozen=True)

    def get_predecessors(self) -> Dict[str, Set[str]]:
        """
        Compute reverse adjacency: { uid -> {nodes that must finish first} }.

        Handles cycle-back edges: if node X routes TO target Y via
        conditional branches, and Y is also in X's predecessors,
        then Y -> X is a back-edge and is removed to prevent deadlock.
        """
        predecessors: Dict[str, Set[str]] = {uid: set() for uid in self.nodes}

        for from_uid, to_uids in self.edges.items():
            for to_uid in to_uids:
                if to_uid in predecessors:
                    predecessors[to_uid].add(from_uid)

        for from_uid, cond in self.conditional_edges.items():
            for target_uid in cond.branches.values():
                if target_uid in predecessors:
                    predecessors[target_uid].add(from_uid)

        for from_uid, cond in self.conditional_edges.items():
            for target_uid in cond.branches.values():
                predecessors[from_uid].discard(target_uid)

        return predecessors

    def get_successors(self, uid: str) -> List[str]:
        """Return unconditional successors of a node."""
        return list(self.edges.get(uid, []))
