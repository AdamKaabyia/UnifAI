from typing import List, Set
from .models import NodeSuggestion, DependencyMatrix


class NodeSuggester:
    """Suggests nodes to resolve validation issues."""

    def suggest_for_channels(self, channels: Set[str], matrix: DependencyMatrix) -> List[NodeSuggestion]:
        """Suggest nodes that can produce any of these channels."""
        # REUSE logic from service.py suggest_producers() but enhanced
        suggestions = []
        seen_nodes = set()  # Avoid duplicates

        for channel in channels:
            if channel in matrix.producer_map:
                for category, type_key in matrix.producer_map[channel]:
                    node_key = (category, type_key)
                    if node_key not in seen_nodes:
                        seen_nodes.add(node_key)
                        suggestions.append(NodeSuggestion(
                            node_type=type_key,
                            category=category,
                            reason=f"Produces '{channel}' needed by existing steps"
                        ))

        return suggestions 