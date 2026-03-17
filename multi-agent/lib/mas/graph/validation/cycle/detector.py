from typing import List, Tuple
from mas.graph.graph_plan import GraphPlan
from ..models import ValidationMessage, MessageSeverity, MessageCode
from ...topology.models import CycleInfo
from ...topology.cycle_algorithms import CycleDetector as TopologyCycleDetector


class CycleDetector:
    """Detects cycles in graph execution flow."""

    def detect_cycles(self, plan: GraphPlan) -> Tuple[List[CycleInfo], List[ValidationMessage]]:
        """Detect all cycles using topology utilities."""
        messages = []

        # Use topology utilities for cycle detection
        topology_detector = TopologyCycleDetector(plan)
        all_cycles = topology_detector.detect_all_cycles()

        # Filter for dangerous cycles using domain logic
        dangerous_cycles = []
        for cycle in all_cycles:
            if topology_detector.is_dangerous_cycle(cycle):
                dangerous_cycles.append(cycle)

        # Create validation messages
        for cycle in dangerous_cycles:
            messages.append(ValidationMessage(
                text=f"Graph contains cycle: {' -> '.join(cycle.cycle_path)}",
                severity=MessageSeverity.ERROR,
                code=MessageCode.CYCLE_DETECTED,
                context={
                    "cycle_path": cycle.cycle_path,
                    "cycle_length": cycle.cycle_length
                }
            ))

        return dangerous_cycles, messages