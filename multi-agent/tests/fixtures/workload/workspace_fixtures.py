"""
Fixtures for Workspace and workload service testing.

Provides fixtures for creating workspace services and workspace objects.
"""

import pytest
from unittest.mock import Mock


@pytest.fixture
def mock_workspace():
    """
    Create a mock workspace for testing.
    
    Returns:
        Mock workspace with variables
    """
    workspace = Mock()
    workspace.variables = {}
    
    def get_variable(key):
        return workspace.variables.get(key)
    
    def set_variable(key, value):
        workspace.variables[key] = value
    
    workspace.get_variable = get_variable
    workspace.set_variable = set_variable
    
    # Mock context
    workspace.context = Mock()
    workspace.context.facts = []
    workspace.context.tasks = []
    workspace.context.results = []
    
    return workspace


@pytest.fixture
def mock_workload_service():
    """
    Create a mock workload service for testing.
    
    Returns:
        Mock workload service with common methods
    """
    workload_service = Mock()
    
    # Mock workspace that gets returned
    mock_workspace = Mock()
    mock_workspace.variables = {}
    mock_workspace.get_variable = lambda k: mock_workspace.variables.get(k)
    mock_workspace.set_variable = lambda k, v: mock_workspace.variables.update({k: v})
    
    # Mock context
    mock_workspace.context = Mock()
    mock_workspace.context.facts = []
    mock_workspace.context.tasks = []
    mock_workspace.context.results = []
    
    workload_service.get_workspace.return_value = mock_workspace
    workload_service.update_workspace = Mock()
    workload_service.get_thread.return_value = None
    workload_service.save_thread = Mock()
    
    return workload_service


@pytest.fixture
def workspace_service(state_view):
    """
    Create a WorkspaceService instance for testing.
    
    NOTE: WorkPlanService is deprecated. Use WorkspaceService.load_work_plan() instead.
    
    Returns:
        WorkspaceService instance (provides work plan operations)
    """
    from mas.elements.nodes.common.workload import UnifiedWorkloadService, StateBoundStorage
    storage = StateBoundStorage(state_view)
    service = UnifiedWorkloadService(storage)
    return service.get_workspace_service()


@pytest.fixture
def workspace_service_with_data(state_view, sample_work_plan):
    """
    Create a WorkspaceService with pre-loaded workplan data.
    
    Returns:
        WorkspaceService with sample workplan loaded
    """
    from mas.elements.nodes.common.workload import UnifiedWorkloadService, StateBoundStorage
    storage = StateBoundStorage(state_view)
    service = UnifiedWorkloadService(storage)
    workspace_service = service.get_workspace_service()
    
    # Save work plan using current API
    workspace_service.save_work_plan(sample_work_plan)
    return workspace_service


@pytest.fixture
def orchestrator_workspace_service(state_view):
    """
    Provide a workspace service bound to the state.
    
    Returns:
        UnifiedWorkloadService bound to state
    """
    from mas.elements.nodes.common.workload import UnifiedWorkloadService, StateBoundStorage
    storage = StateBoundStorage(state_view)
    return UnifiedWorkloadService(storage)
