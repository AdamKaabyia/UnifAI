from typing import Set, List, Tuple
from mas.graph.graph_plan import GraphPlan
from ..models import ValidationMessage, MessageSeverity, MessageCode
from ...topology.connectivity_analyzer import ConnectivityAnalyzer


class OrphanDetector:
    """Detects orphaned steps with no connections."""
    
    def detect_orphans(self, plan: GraphPlan) -> Tuple[Set[str], List[ValidationMessage]]:
        """Find steps with no dependencies or dependents."""
        messages = []
        
        # Use topology utilities for connectivity analysis
        connectivity_analyzer = ConnectivityAnalyzer(plan)
        orphaned_steps = connectivity_analyzer.find_orphaned_nodes()
        
        for orphan in orphaned_steps:
            messages.append(ValidationMessage(
                text=f"Step '{orphan}' is orphaned (no dependencies or dependents)",
                severity=MessageSeverity.WARNING,
                code=MessageCode.ORPHANED_STEP,
                context={"step_id": orphan}
            ))
        
        return orphaned_steps, messages