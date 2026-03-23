from typing import List, Set, Dict, NamedTuple
from mas.graph.graph_plan import GraphPlan
from ..interfaces import FixSuggestionProvider
from ..models import ValidationReport, MessageCode
from ..fix_models import FixSuggestion, FixType
from ..settings import ValidationSettings
from .checker import RequiredNodesChecker
from .models import NodePosition, RequiredNodeFixType


class NodeFixConfig(NamedTuple):
    """Configuration for generating fix suggestions for a specific node position."""
    position: NodePosition
    fix_type: RequiredNodeFixType
    default_message_code: MessageCode
    text_template: str


class RequiredNodesFixProvider(FixSuggestionProvider):
    """Provides fix suggestions for missing required node types."""

    # Configuration for different node position types
    _FIX_CONFIGS = {
        NodePosition.START: NodeFixConfig(
            position=NodePosition.START,
            fix_type=RequiredNodeFixType.ADD_REQUIRED_START,
            default_message_code=MessageCode.MISSING_START_NODE,
            text_template="Add a '{node_type}' node as an entry point to the workflow"
        ),
        NodePosition.END: NodeFixConfig(
            position=NodePosition.END,
            fix_type=RequiredNodeFixType.ADD_REQUIRED_END,
            default_message_code=MessageCode.MISSING_END_NODE,
            text_template="Add a '{node_type}' node as an exit point from the workflow"
        ),
        NodePosition.ANY: NodeFixConfig(
            position=NodePosition.ANY,
            fix_type=RequiredNodeFixType.ADD_REQUIRED_ANYWHERE,
            default_message_code=MessageCode.MISSING_REQUIRED_NODE,
            text_template="Add a '{node_type}' node to the workflow"
        )
    }

    def __init__(self, settings: ValidationSettings = None, *args, **kwargs):
        self._settings = settings or ValidationSettings()
        self._checker = RequiredNodesChecker(
            required_start_nodes=self._settings.required_start_nodes,
            required_end_nodes=self._settings.required_end_nodes,
            required_any_nodes=self._settings.required_any_nodes
        )

    def suggest_fixes(
        self, 
        plan: GraphPlan, 
        validation_report: ValidationReport | None = None
    ) -> List[FixSuggestion]:
        """Suggest fixes for missing required node types."""
        suggestions = []
        
        if not validation_report or not validation_report.details:
            return suggestions

        required_node_issues = validation_report.details.get("required_node_issues", [])
        if not required_node_issues:
            return suggestions

        # Extract message codes from validation report
        message_codes = self._extract_message_codes(validation_report)

        # Generate suggestions for each issue using configuration-driven approach
        for issue_data in required_node_issues:
            node_position = issue_data.get("node_type")
            expected_type = issue_data.get("expected")
            
            if not expected_type or node_position not in self._FIX_CONFIGS:
                continue
                
            suggestion = self._create_fix_suggestion(
                expected_type, node_position, plan, message_codes
            )
            if suggestion:
                suggestions.append(suggestion)

        return suggestions

    def _extract_message_codes(self, validation_report: ValidationReport) -> Dict[str, MessageCode]:
        """Extract message codes from validation report."""
        codes = {}
        for message in validation_report.messages:
            if message.code:
                expected = message.context.get('expected', 'general')
                codes[expected] = message.code
        return codes

    def _create_fix_suggestion(
        self,
        expected_type: str,
        node_position: NodePosition,
        plan: GraphPlan,
        message_codes: Dict[str, MessageCode]
    ) -> FixSuggestion | None:
        """Create a fix suggestion for a missing required node."""
        config = self._FIX_CONFIGS.get(node_position)
        if not config:
            return None
            
        code = message_codes.get(expected_type, config.default_message_code)
        
        return FixSuggestion(
            text=config.text_template.format(node_type=expected_type),
            fix_type=FixType.ADD_NODE,
            code=code,
            context={
                "required_node_type": expected_type,
                "position": config.position,
                "fix_type": config.fix_type,
                "node_category": self._get_node_category(expected_type, plan),
                "suggested_node_type": expected_type
            },
            priority=1
        )



    def _get_node_category(self, node_type: str, plan: GraphPlan = None) -> str:
        """Get the likely category for a node type."""
        # First, try to find an existing step with this type to get its actual category
        if plan:
            for step in plan.steps:
                if step.type_key == node_type:
                    return step.category.value
