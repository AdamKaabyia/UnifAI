"""
Fixtures for Task objects and task-related testing.

Provides fixtures for creating tasks with various configurations.
"""

import pytest
from tests.factories.task_factory import TaskFactory


@pytest.fixture
def sample_task():
    """
    Create a sample Task for testing.
    
    Returns:
        Simple Task instance
    """
    return TaskFactory.create_simple_task(
        content="Analyze Q4 sales data and create a summary report",
        thread_id="test_thread_789",
        created_by="user_node"
    )


@pytest.fixture
def sample_response_task():
    """
    Create a sample response Task for testing.
    
    Returns:
        Task configured as a response
    """
    return TaskFactory.create_response_task(
        response_content='{"success": true, "data": {"revenue": 1000000}}',
        correlation_task_id="task_abc123",
        thread_id="test_thread_789",
        created_by="data_processor",
        success=True,
        result_data={"revenue": 1000000}
    )


@pytest.fixture
def sample_ambiguous_response_task():
    """
    Create a sample ambiguous response Task for testing.
    
    Returns:
        Task with ambiguous response content
    """
    from mas.elements.nodes.common.workload import Task
    
    return Task(
        content="I found the data but it's in XML format. Should I convert it?",
        thread_id="test_thread_789",
        created_by="data_processor",
        correlation_task_id="task_def456"
    )


@pytest.fixture
def integration_task_factory():
    """
    Provide a factory for creating tasks for integration testing.
    
    Returns:
        TaskFactory.create_simple_task callable
    """
    return TaskFactory.create_simple_task
