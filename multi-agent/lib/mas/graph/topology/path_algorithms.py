"""
Path enumeration for GraphPlan objects.

Clean OOP design for path analysis.
"""

from typing import Dict, Set, List
from .graph_builder import GraphAnalyzer


class PathEnumerator:
    """
    Path enumerator that works with GraphPlan objects.
    
    Clean interface for path enumeration operations.
    """
    
    def __init__(self, plan: 'GraphPlan'):
        self.analyzer = GraphAnalyzer(plan)
    
    def enumerate_paths(self) -> Dict[str, List[str]]:
        """Generate all execution paths through the graph."""
        paths = {}
        root_nodes = self.analyzer.get_root_nodes()

        # DFS from each root
        for root in root_nodes:
            self._dfs_path_enumeration(root, [], paths)

        return paths
    
    def _dfs_path_enumeration(
        self,
        current: str,
        path: List[str],
        paths: Dict[str, List[str]]
    ) -> None:
        """DFS traversal to enumerate paths."""
        # Check for cycle in current path
        if current in path:
            # Found cycle - record cyclic path and stop recursion
            path_id = f"path_{len(paths) + 1}_cyclic"
            paths[path_id] = path + [current]
            return
        
        current_path = path + [current]
        successors = self.analyzer.adjacency.get(current, set())

        if not successors:
            # Terminal node - complete path
            path_id = f"path_{len(paths) + 1}"
            paths[path_id] = current_path
        else:
            # Continue to successors
            for next_node in successors:
                self._dfs_path_enumeration(next_node, current_path, paths)
    
