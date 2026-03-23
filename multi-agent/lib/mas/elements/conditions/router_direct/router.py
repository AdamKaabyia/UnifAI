from ..common.base_condition import BaseCondition
from ..common.models import ConditionOutputSchema, BranchType, DirectBranchDef
from mas.graph.state.state_view import StateView
from mas.graph.state.graph_state import Channel
from mas.core.iem.utils import get_outgoing_targets


class RouterDirectCondition(BaseCondition):
    """
    IEM-based router condition that routes to nodes receiving packets.
    """

    READS = {Channel.INTER_PACKETS}

    def run(self, state: StateView):
        """
        Route to nodes that have been receiving packets from this node.
        
        Returns:
            - Node UID(s) if targets exist
            - END if no targets (graceful termination instead of None crash)
        """
        if not self.context:
            print("⚠️ [ROUTER] No context available - ending graph")
            return "END"

        targets = get_outgoing_targets(state, self.context)
        print(targets)
        if not targets:
            print("⚠️ [ROUTER] No outgoing targets found - ending graph gracefully")
            return "END"

        if len(targets) == 1:
            return list(targets)[0]

        # Return as tuple for multiple targets
        return tuple(sorted(targets))

    def __repr__(self) -> str:
        return "<RouterDirectCondition: IEM-based routing>"

    @classmethod
    def get_output_schema(cls) -> ConditionOutputSchema:
        """
        RouterDirectCondition returns direct node UIDs based on IEM analysis.
        """
        return ConditionOutputSchema(
            branch_type=BranchType.DIRECT,
            direct_config=DirectBranchDef(
                description="Routes to nodes based on IEM communication patterns"
            ),
            description="IEM-based router that follows actual packet communication"
        )
