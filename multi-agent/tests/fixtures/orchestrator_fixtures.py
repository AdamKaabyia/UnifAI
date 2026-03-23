"""
Comprehensive test fixtures for orchestrator system testing.

This module provides fixtures for all orchestrator components including:
- WorkPlan and WorkItem models
- UnifiedWorkloadService (replaces deprecated WorkPlanService)
- OrchestratorPhaseProvider
- Orchestration tools
- PlanAndExecuteStrategy
- OrchestratorNode

Note: WorkPlanService is DEPRECATED. Use UnifiedWorkloadService.get_workspace_service() instead.
"""

import pytest
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from unittest.mock import Mock, MagicMock, patch

# Core imports
from mas.elements.tools.common.base_tool import BaseTool
from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.elements.nodes.common.agent.primitives import AgentObservation, AgentAction
from mas.elements.nodes.common.workload import (
    WorkPlan, WorkItem, WorkItemStatus, WorkItemKind,
    WorkItemResult, ToolArguments, WorkPlanStatus, Task,
    UnifiedWorkloadService, InMemoryStorage
)
from mas.elements.nodes.orchestrator.orchestrator_phase_provider import (
    OrchestratorPhaseProvider, OrchestratorPhase
)
from mas.elements.nodes.common.agent.phases.phase_definition import PhaseDefinition, PhaseSystem
from tests.conftest import create_step_context
from mas.elements.nodes.common.agent.phases.phase_protocols import PhaseState, create_phase_state


# =============================================================================
# WORKPLAN MODEL FIXTURES
# =============================================================================

@pytest.fixture
def sample_work_item():
    """Create a sample WorkItem for testing."""
    return WorkItem(
        id="test_item_1",
        title="Test Work Item",
        description="A test work item for unit testing",
        dependencies=["dependency_1"],
        status=WorkItemStatus.PENDING,
        kind=WorkItemKind.REMOTE,
        assigned_uid="test_node_1",
        tool="test_tool",
        args=ToolArguments({"param1": "value1"}),
        retry_count=0,
        max_retries=3
    )


@pytest.fixture
def sample_work_item_with_result():
    """Create a WorkItem with result for testing."""
    result = WorkItemResult(
        success=True,
        content="Task completed successfully",
        data={"output": "test result"},
        metadata={"execution_time": 1.5}
    )
    
    return WorkItem(
        id="completed_item",
        title="Completed Work Item",
        description="A completed work item",
        status=WorkItemStatus.DONE,
        kind=WorkItemKind.LOCAL,
        result_ref=result
    )


@pytest.fixture
def sample_work_plan():
    """Create a sample WorkPlan for testing."""
    items = {
        "item_1": WorkItem(
            id="item_1",
            title="First Item",
            description="First work item",
            dependencies=[],
            status=WorkItemStatus.PENDING,
            kind=WorkItemKind.REMOTE
        ),
        "item_2": WorkItem(
            id="item_2", 
            title="Second Item",
            description="Second work item",
            dependencies=["item_1"],
            status=WorkItemStatus.PENDING,
            kind=WorkItemKind.LOCAL
        ),
        "item_3": WorkItem(
            id="item_3",
            title="Third Item", 
            description="Third work item",
            dependencies=["item_2"],
            status=WorkItemStatus.PENDING,
            kind=WorkItemKind.REMOTE
        )
    }
    
    return WorkPlan(
        summary="Test Work Plan",
        owner_uid="test_orchestrator",
        thread_id="test_thread_123",
        items=items
    )


@pytest.fixture
def complex_work_plan():
    """Create a complex WorkPlan with various statuses for testing."""
    items = {
        "ready_item": WorkItem(
            id="ready_item",
            title="Ready Item",
            description="Item ready for execution",
            dependencies=[],
            status=WorkItemStatus.PENDING,
            kind=WorkItemKind.LOCAL
        ),
        "waiting_item": WorkItem(
            id="waiting_item",
            title="Waiting Item", 
            description="Item in progress (remote delegation)",
            dependencies=[],
            status=WorkItemStatus.IN_PROGRESS,
            kind=WorkItemKind.REMOTE,
            assigned_uid="remote_node",
            correlation_task_id="task_123"
        ),
        "done_item": WorkItem(
            id="done_item",
            title="Done Item",
            description="Completed item",
            dependencies=[],
            status=WorkItemStatus.DONE,
            kind=WorkItemKind.REMOTE,
            result_ref=WorkItemResult(success=True, content="Completed")
        ),
        "failed_item": WorkItem(
            id="failed_item",
            title="Failed Item",
            description="Failed item",
            dependencies=[],
            status=WorkItemStatus.FAILED,
            kind=WorkItemKind.LOCAL,
            error="Task failed due to error",
            retry_count=3
        ),
        "blocked_item": WorkItem(
            id="blocked_item",
            title="Blocked Item",
            description="Item blocked by dependencies",
            dependencies=["pending_dependency"],
            status=WorkItemStatus.PENDING,
            kind=WorkItemKind.LOCAL
        )
    }
    
    return WorkPlan(
        summary="Complex Test Work Plan",
        owner_uid="test_orchestrator",
        thread_id="test_thread_456", 
        items=items
    )


# =============================================================================
# WORKSPACE AND SERVICE FIXTURES
# =============================================================================

@pytest.fixture
def mock_workspace():
    """Create a mock workspace for testing."""
    workspace = Mock()
    workspace.variables = {}
    
    def get_variable(key):
        return workspace.variables.get(key)
    
    def set_variable(key, value):
        workspace.variables[key] = value
    
    workspace.get_variable = get_variable
    workspace.set_variable = set_variable
    
    return workspace


@pytest.fixture
def mock_workload_service():
    """Create a mock workload service for testing."""
    workload_service = Mock()
    
    # Mock workspace that gets returned
    mock_workspace = Mock()
    mock_workspace.variables = {}
    mock_workspace.get_variable = lambda k: mock_workspace.variables.get(k)
    mock_workspace.set_variable = lambda k, v: mock_workspace.variables.update({k: v})
    
    workload_service.get_workspace.return_value = mock_workspace
    workload_service.update_workspace = Mock()
    
    return workload_service

@pytest.fixture
def real_workload_service():
    """
    Create REAL UnifiedWorkloadService with in-memory storage.
    
    USE THIS instead of mock_workload_service for meaningful tests.
    Provides real behavior testing with isolated in-memory storage.
    """
    storage = InMemoryStorage()
    return UnifiedWorkloadService(storage)


@pytest.fixture
def workspace_service_real(real_workload_service):
    """
    Get real WorkspaceService from unified service.
    
    This is the CURRENT API pattern:
        workspace_service = workload_service.get_workspace_service()
        work_plan = workspace_service.load_work_plan(thread_id, owner_uid)
    """
    return real_workload_service.get_workspace_service()


@pytest.fixture
def work_plan_service(mock_workload_service):
    """
    DEPRECATED: Use workspace_service_real instead.
    Create a WorkPlanService instance (for backward compatibility).
    """
    from mas.elements.nodes.common.workload.workplan import WorkPlanService as LegacyWorkPlanService
    # WorkPlanService now requires workspace_service and thread_service
    # This is a simplified mock version
    return Mock()


@pytest.fixture
def work_plan_service_with_data(mock_workload_service, sample_work_plan):
    """
    DEPRECATED: Use workspace_service_real with save_work_plan instead.
    Create a WorkPlanService with pre-loaded data (for backward compatibility).
    """
    service = Mock()
    service.load = Mock(return_value=sample_work_plan)
    return service


# =============================================================================
# PHASE PROVIDER FIXTURES
# =============================================================================

@pytest.fixture
def mock_domain_tools():
    """Create mock domain tools for testing."""
    tool1 = Mock(spec=BaseTool)
    tool1.name = "analyze_data_tool"
    tool1.description = "Analyzes data"
    
    tool2 = Mock(spec=BaseTool)
    tool2.name = "create_report_tool"
    tool2.description = "Creates reports"
    
    return [tool1, tool2]


@pytest.fixture
def mock_orchestrator_dependencies():
    """Create mock dependencies for OrchestratorPhaseProvider."""
    workload_service = Mock()
    get_workload_service = Mock(return_value=workload_service)
    get_adjacent_nodes = Mock(return_value={
        "node_1": {"type": "data_processor", "specialization": "Data processing"},
        "node_2": {"type": "report_generator", "specialization": "Report generation"}
    })
    send_task = Mock(return_value="packet_123")
    
    return {
        "get_workload_service": get_workload_service,
        "get_adjacent_nodes": get_adjacent_nodes,
        "send_task": send_task,
        "node_uid": "test_orchestrator",
        "thread_id": "test_thread"
    }


@pytest.fixture
def orchestrator_phase_provider(mock_domain_tools, mock_orchestrator_dependencies):
    """Create an OrchestratorPhaseProvider for testing."""
    return OrchestratorPhaseProvider(
        domain_tools=mock_domain_tools,
        **mock_orchestrator_dependencies
    )


# =============================================================================
# ORCHESTRATION TOOL FIXTURES
# =============================================================================

@pytest.fixture
def mock_tool_dependencies():
    """Create mock dependencies for orchestration tools."""
    # Create mock workload service for SOLID design
    workload_service = Mock()
    workspace = Mock()
    workspace.variables = {}
    workspace.get_variable = lambda k: workspace.variables.get(k)
    workspace.set_variable = lambda k, v: workspace.variables.update({k: v})
    workload_service.get_workspace.return_value = workspace
    workload_service.update_workspace = Mock()
    
    # Create mock thread for delegation testing
    from mas.elements.nodes.common.workload import Thread
    mock_thread = Thread(
        title="Test Thread",
        objective="Test objective",
        initiator="test_orchestrator"
    )
    mock_thread.thread_id = "test_thread"
    workload_service.get_thread.return_value = mock_thread
    workload_service.save_thread = Mock()
    
    return {
        "get_workload_service": lambda: workload_service,
        "get_thread_id": lambda: "test_thread",  # Keep for backward compatibility
        "get_current_thread": lambda: mock_thread,  # New enhanced injection
        "get_owner_uid": lambda: "test_orchestrator",
        "send_task": Mock(return_value="packet_123"),
        "check_adjacency": lambda uid: uid in ["node_1", "node_2"],
        "get_adjacent_nodes": lambda: {"node_1": {}, "node_2": {}}
    }


# =============================================================================
# STRATEGY FIXTURES
# =============================================================================

@pytest.fixture
def mock_llm_chat():
    """Create a mock LLM chat function for strategy testing."""
    def _mock_chat(messages: List[ChatMessage], tools: List[BaseTool]) -> ChatMessage:
        # Default response that creates a work plan
        return ChatMessage(
            role=Role.ASSISTANT,
            content="I'll create a work plan for this task.",
            tool_calls=[{
                "name": "create_or_update_workplan",
                "args": {
                    "summary": "Test work plan",
                    "items": [{
                        "id": "test_item",
                        "title": "Test Item",
                        "description": "A test work item",
                        "dependencies": [],
                        "kind": "REMOTE"
                    }]
                },
                "tool_call_id": "call_123"
            }]
        )
    return _mock_chat


@pytest.fixture
def mock_output_parser():
    """Create a mock output parser for strategy testing."""
    parser = Mock()
    parser.parse.return_value = [
        AgentAction(
            id="action_123",
            tool="create_or_update_workplan",
            tool_input={
                "summary": "Test work plan",
                "items": [{
                    "id": "test_item",
                    "title": "Test Item", 
                    "description": "A test work item",
                    "dependencies": [],
                    "kind": "REMOTE"
                }]
            },
            reasoning="Creating work plan"
        )
    ]
    return parser


# =============================================================================
# ORCHESTRATOR NODE FIXTURES
# =============================================================================

@pytest.fixture
def mock_llm():
    """Create a mock LLM for orchestrator node testing."""
    llm = Mock()
    llm.chat.return_value = ChatMessage(
        role=Role.ASSISTANT,
        content="I'll help you with this task."
    )
    return llm


@pytest.fixture
def sample_task():
    """Create a sample Task for testing."""
    return Task(
        content="Analyze Q4 sales data and create a summary report",
        thread_id="test_thread_789",
        created_by="user_node",
        should_respond=True,
        response_to="user_node"
    )


@pytest.fixture
def sample_response_task():
    """Create a sample response Task for testing."""
    return Task(
        content='{"success": true, "data": {"revenue": 1000000}}',
        thread_id="test_thread_789",
        created_by="data_processor",
        correlation_task_id="task_abc123",
        result={"success": True, "data": {"revenue": 1000000}}
    )


@pytest.fixture
def sample_ambiguous_response_task():
    """Create a sample ambiguous response Task for testing."""
    return Task(
        content="I found the data but it's in XML format. Should I convert it?",
        thread_id="test_thread_789",
        created_by="data_processor",
        correlation_task_id="task_def456"
    )


# =============================================================================
# MOCK PACKET FIXTURES
# =============================================================================

@pytest.fixture
def mock_task_packet(sample_task):
    """Create a mock task packet for testing."""
    packet = Mock()
    packet.id = "packet_123"
    packet.extract_task.return_value = sample_task
    return packet


@pytest.fixture
def mock_response_packet(sample_response_task):
    """Create a mock response packet for testing."""
    packet = Mock()
    packet.id = "packet_456"
    packet.extract_task.return_value = sample_response_task
    return packet


# =============================================================================
# AGENT OBSERVATION FIXTURES
# =============================================================================

@pytest.fixture
def sample_agent_observations():
    """Create sample agent observations for testing."""
    return [
        AgentObservation(
            action_id="action_123",
            tool="create_or_update_workplan",
            output='{"success": true, "plan_summary": "Test plan", "items_created": 3}',
            success=True,
            error=None,
            execution_time=0.5
        ),
        AgentObservation(
            action_id="action_456",
            tool="delegate_task",
            output='{"success": true, "task_id": "task_789", "dst_uid": "node_1"}',
            success=True,
            error=None,
            execution_time=0.3
        )
    ]


@pytest.fixture
def failed_agent_observation():
    """Create a failed agent observation for testing."""
    return AgentObservation(
        action_id="action_fail",
        tool="delegate_task",
        output="",
        success=False,
        error="Node not available",
        execution_time=0.1
    )


# =============================================================================
# EDGE CASE FIXTURES
# =============================================================================

@pytest.fixture
def empty_work_plan():
    """Create an empty WorkPlan for edge case testing."""
    return WorkPlan(
        summary="Empty Work Plan",
        owner_uid="test_orchestrator",
        thread_id="empty_thread",
        items={}
    )


@pytest.fixture
def circular_dependency_work_plan():
    """Create a WorkPlan with circular dependencies for edge case testing."""
    items = {
        "item_a": WorkItem(
            id="item_a",
            title="Item A",
            description="Depends on B",
            dependencies=["item_b"],
            status=WorkItemStatus.PENDING,
            kind=WorkItemKind.LOCAL
        ),
        "item_b": WorkItem(
            id="item_b",
            title="Item B", 
            description="Depends on C",
            dependencies=["item_c"],
            status=WorkItemStatus.PENDING,
            kind=WorkItemKind.LOCAL
        ),
        "item_c": WorkItem(
            id="item_c",
            title="Item C",
            description="Depends on A (circular)",
            dependencies=["item_a"],
            status=WorkItemStatus.PENDING,
            kind=WorkItemKind.LOCAL
        )
    }
    
    return WorkPlan(
        summary="Circular Dependency Plan",
        owner_uid="test_orchestrator",
        thread_id="circular_thread",
        items=items
    )


@pytest.fixture
def max_retry_work_item():
    """Create a WorkItem that has reached max retries."""
    return WorkItem(
        id="max_retry_item",
        title="Max Retry Item",
        description="Item that has reached maximum retries",
        status=WorkItemStatus.FAILED,
        kind=WorkItemKind.REMOTE,
        retry_count=3,
        max_retries=3,
        error="Maximum retries exceeded"
    )


# =============================================================================
# PERFORMANCE TEST FIXTURES
# =============================================================================

@pytest.fixture
def large_work_plan():
    """Create a large WorkPlan for performance testing."""
    items = {}
    for i in range(100):
        items[f"item_{i}"] = WorkItem(
            id=f"item_{i}",
            title=f"Item {i}",
            description=f"Work item number {i}",
            dependencies=[f"item_{i-1}"] if i > 0 else [],
            status=WorkItemStatus.PENDING,
            kind=WorkItemKind.REMOTE if i % 2 == 0 else WorkItemKind.LOCAL
        )
    
    return WorkPlan(
        summary="Large Work Plan",
        owner_uid="test_orchestrator",
        thread_id="large_thread",
        items=items
    )


# =============================================================================
# UTILITY FIXTURES
# =============================================================================

@pytest.fixture
def freeze_time():
    """Freeze time for consistent testing."""
    with patch('elements.nodes.common.workload.workplan.datetime') as mock_datetime:
        mock_datetime.utcnow.return_value = datetime(2024, 1, 1, 12, 0, 0)
        mock_datetime.utcnow().isoformat.return_value = "2024-01-01T12:00:00"
        yield mock_datetime


@pytest.fixture
def capture_debug_output():
    """Capture debug print statements for testing."""
    captured_output = []
    
    def mock_print(*args, **kwargs):
        captured_output.append(" ".join(str(arg) for arg in args))
    
    with patch('builtins.print', side_effect=mock_print):
        yield captured_output


# =============================================================================
# PARAMETRIZED FIXTURES
# =============================================================================

@pytest.fixture(params=[
    WorkItemStatus.PENDING,
    WorkItemStatus.IN_PROGRESS, 
    WorkItemStatus.DONE,
    WorkItemStatus.FAILED
])
def work_item_status(request):
    """Parametrized fixture for all work item statuses."""
    return request.param


@pytest.fixture(params=[
    WorkItemKind.LOCAL,
    WorkItemKind.REMOTE
])
def work_item_kind(request):
    """Parametrized fixture for all work item kinds."""
    return request.param


@pytest.fixture(params=[
    OrchestratorPhase.PLANNING,
    OrchestratorPhase.ALLOCATION,
    OrchestratorPhase.EXECUTION,
    OrchestratorPhase.MONITORING,
    OrchestratorPhase.SYNTHESIS
])
def orchestrator_phase(request):
    """Parametrized fixture for all orchestrator phases."""
    return request.param


# =============================================================================
# STEP CONTEXT FIXTURES
# =============================================================================

@pytest.fixture
def orchestrator_step_context():
    """Create a StepContext specifically for orchestrator node testing."""
    return create_step_context(
        uid="test_orchestrator",
        adjacent_nodes=["data_processor", "report_generator", "analyzer"]
    )


@pytest.fixture
def orchestrator_step_context_with_many_nodes():
    """Create a StepContext with many adjacent nodes for testing."""
    adjacent_nodes = [f"node_{i}" for i in range(10)]
    return create_step_context(
        uid="test_orchestrator", 
        adjacent_nodes=adjacent_nodes
    )


@pytest.fixture
def orchestrator_step_context_isolated():
    """Create a StepContext with no adjacent nodes for testing."""
    return create_step_context(uid="test_orchestrator", adjacent_nodes=[])


@pytest.fixture
def orchestrator_node_with_state(mock_llm, orchestrator_step_context, state_view):
    """Create an OrchestratorNode with both context and state properly set up."""
    from mas.elements.nodes.orchestrator.orchestrator_node import OrchestratorNode
    
    node = OrchestratorNode(llm=mock_llm)
    node.set_context(orchestrator_step_context)  # Set up context for uid access
    node._state = state_view  # Set up state for workspace operations
    return node
