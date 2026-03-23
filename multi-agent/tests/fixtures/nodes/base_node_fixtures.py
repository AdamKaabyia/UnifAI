"""
Base fixtures common to all nodes.

Provides fixtures that are used across different node types.
"""

import pytest
from unittest.mock import Mock


@pytest.fixture
def mock_tool_executor_manager():
    """
    Mock ToolExecutorManager for testing.
    
    Returns:
        Mock manager with common methods
    """
    manager = Mock()
    manager.has_tool.return_value = True
    manager.execute_requests_async.return_value = Mock()
    manager.get_health.return_value = {"status": "healthy"}
    manager.metrics = {"total_executions": 0, "success_rate": 1.0}
    return manager


@pytest.fixture
def mock_agent_action_executor():
    """
    Mock agent action executor for testing.
    
    Returns:
        Mock executor with execute methods
    """
    from mas.elements.nodes.common.agent.primitives import AgentObservation
    
    executor = Mock()
    executor.execute.return_value = AgentObservation(
        action_id="action-123",
        tool="test_tool",
        output="Mock tool result",
        success=True,
        error=None,
        execution_time=0.1
    )
    executor.execute_batch.return_value = [
        AgentObservation(
            action_id="action-123",
            tool="test_tool",
            output="Mock tool result",
            success=True,
            error=None,
            execution_time=0.1
        )
    ]
    return executor


@pytest.fixture
def sample_config():
    """
    Sample configuration for testing.
    
    Returns:
        Dict with common config values
    """
    return {
        "max_steps": 10,
        "timeout": 30,
        "retry_attempts": 3,
        "debug": True
    }
