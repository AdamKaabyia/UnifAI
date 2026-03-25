"""
Graph topology analysis utilities.

Clean OOP design for graph analysis with GraphPlan objects.
"""

# Import only the core models that don't have circular dependencies
from .models import StepTopology, FinalizerPathInfo, FinalizerDistance

# Other topology utilities can be imported directly from their modules when needed
# This prevents circular import issues while maintaining clean architecture

__all__ = [
    'StepTopology',
    'FinalizerPathInfo', 
    'FinalizerDistance',
]

# For other topology utilities, import directly from their modules:
# from mas.graph.topology.finalizer_analyzer import FinalizerAnalyzer
# from mas.graph.topology.graph_traversal import GraphTraversal
# from mas.graph.topology.graph_builder import GraphAnalyzer, EdgeType
# etc.
