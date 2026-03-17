"""
Fixtures for WorkPlan objects and workplan-related testing.

Provides fixtures for creating workplans with various configurations.
"""

import pytest
from tests.factories.workplan_factory import WorkPlanFactory


@pytest.fixture
def sample_work_item():
    """
    Create a sample WorkItem for testing.
    
    Returns:
        WorkItem instance
    """
    from mas.elements.nodes.common.workload import WorkItemStatus, WorkItemKind, ToolArguments
    
    return WorkPlanFactory.create_work_item(
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
    """
    Create a WorkItem with result for testing.
    
    Returns:
        Completed WorkItem with result
    """
    return WorkPlanFactory.create_work_item_with_result(
        id="completed_item",
        title="Completed Work Item",
        success=True,
        result_content="Task completed successfully"
    )


@pytest.fixture
def sample_work_plan():
    """
    Create a sample WorkPlan for testing.
    
    Returns:
        Simple WorkPlan with sequential items
    """
    return WorkPlanFactory.create_simple_work_plan(
        item_count=3,
        owner_uid="test_orchestrator",
        thread_id="test_thread_123",
        summary="Test Work Plan"
    )


@pytest.fixture
def complex_work_plan():
    """
    Create a complex WorkPlan with various statuses for testing.
    
    Returns:
        WorkPlan with items in different states
    """
    return WorkPlanFactory.create_complex_work_plan(
        owner_uid="test_orchestrator",
        thread_id="test_thread_456"
    )


@pytest.fixture
def empty_work_plan():
    """
    Create an empty WorkPlan for edge case testing.
    
    Returns:
        WorkPlan with no items
    """
    from mas.elements.nodes.common.workload import WorkPlan
    
    return WorkPlan(
        summary="Empty Work Plan",
        owner_uid="test_orchestrator",
        thread_id="empty_thread",
        items={}
    )


@pytest.fixture
def large_work_plan():
    """
    Create a large WorkPlan for performance testing.
    
    Returns:
        WorkPlan with 100 sequential items
    """
    return WorkPlanFactory.create_simple_work_plan(
        item_count=100,
        owner_uid="test_orchestrator",
        thread_id="large_thread",
        summary="Large Work Plan"
    )
