from typing import Dict, List
from mas.graph.graph_plan import GraphPlan
from ...topology.path_algorithms import PathEnumerator as TopologyPathEnumerator


class PathEnumerator:
    """Enumerates all possible execution paths through a graph."""

    def enumerate_paths(self, plan: GraphPlan) -> Dict[str, List[str]]:
        """Generate all execution paths through the graph."""
        # Use topology utilities for path enumeration
        topology_enumerator = TopologyPathEnumerator(plan)
        return topology_enumerator.enumerate_paths()