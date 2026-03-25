"""
Simplified unit tests for OrchestratorNode.

Focus on testing BEHAVIOR not implementation details.
Uses GENERIC test helpers from tests.base.test_helpers.
"""

import pytest
from unittest.mock import Mock

from mas.elements.nodes.orchestrator.orchestrator_node import OrchestratorNode
from mas.elements.nodes.common.workload import (
    UnifiedWorkloadService, InMemoryStorage, WorkItem, WorkItemKind, WorkItemStatus
)

# Import GENERIC helpers (work for ALL nodes)
from tests.base.test_helpers import (
    setup_node_with_state,
    setup_node_with_context,
    assert_has_workload_capability,
    assert_has_iem_capability,
    assert_has_llm_capability,
    assert_has_agent_capability
)


@pytest.mark.unit
@pytest.mark.orchestrator
class TestOrchestratorBasics:
    """Test basic orchestrator functionality."""
    
    def test_orchestrator_initialization(self, mock_llm):
        """Test basic orchestrator creation."""
        node = OrchestratorNode(
            llm=mock_llm,
            system_message="Test orchestrator",
            max_rounds=10
        )
        
        assert node.llm == mock_llm
        assert node.domain_specialization == "Test orchestrator"
        assert node.max_rounds == 10
        assert isinstance(node._updated_threads, set)
    
    def test_orchestrator_with_domain_tools(self, mock_llm, basic_test_tools):
        """Test orchestrator with domain tools."""
        node = OrchestratorNode(
            llm=mock_llm,
            tools=basic_test_tools,
            system_message="Specialized orchestrator"
        )
        
        assert len(node.base_tools) == len(basic_test_tools)
    
    def test_system_message_includes_orchestration(self, mock_llm):
        """Test that system message includes orchestration instructions."""
        node = OrchestratorNode(
            llm=mock_llm,
            system_message="I analyze documents"
        )
        
        # Build complete system message
        full_message = node._build_complete_system_message()
        
        # Should include both domain and orchestration
        assert "I analyze documents" in full_message
        # Should have more than just the domain message (orchestration added)
        assert len(full_message) > len("I analyze documents")


@pytest.mark.unit  
@pytest.mark.orchestrator
class TestOrchestratorWorkloadCapabilities:
    """Test orchestrator's workload management capabilities."""
    
    def test_orchestrator_has_workload_service_access(self, mock_llm):
        """Orchestrator should have access to workload service via mixin."""
        node = OrchestratorNode(llm=mock_llm)
        
        # ✅ GENERIC: Use helper for state setup (works for ALL nodes)
        setup_node_with_state(node)
        
        # ✅ GENERIC: Assert capabilities (works for ALL WorkloadCapable nodes)
        assert_has_workload_capability(node)
        
        # Should be able to get workload service
        service = node.get_workload_service()
        assert service is not None
    
    def test_orchestrator_can_access_workspace_service(self, mock_llm):
        """Orchestrator should access workspace service via .workspaces property."""
        node = OrchestratorNode(llm=mock_llm)
        
        # ✅ GENERIC: Use helper (works for ALL WorkloadCapable nodes)
        setup_node_with_state(node)
        
        # Access workspace service
        workspace_service = node.workspaces
        
        assert workspace_service is not None
        # Should be able to create work plans
        plan = workspace_service.create_work_plan("thread_1", "orch1")
        assert plan.owner_uid == "orch1"
        assert plan.thread_id == "thread_1"
    
    def test_orchestrator_can_access_thread_service(self, mock_llm):
        """Orchestrator should access thread service via .threads property."""
        node = OrchestratorNode(llm=mock_llm)
        
        # ✅ GENERIC: Use helper (works for ALL WorkloadCapable nodes)
        setup_node_with_state(node)
        
        # Access thread service
        thread_service = node.threads
        
        assert thread_service is not None
        # Should be able to create threads
        thread = thread_service.create_root_thread("Test", "Objective", "orch1")
        assert thread.title == "Test"
        assert thread.initiator == "orch1"
    
    def test_orchestrator_updated_threads_tracking(self, mock_llm):
        """Verify _updated_threads set is properly initialized."""
        node = OrchestratorNode(llm=mock_llm)
        
        # Should have empty set on initialization
        assert isinstance(node._updated_threads, set)
        assert len(node._updated_threads) == 0
        
        # Can add threads
        node._updated_threads.add("thread_1")
        node._updated_threads.add("thread_2")
        assert len(node._updated_threads) == 2
        
        # Can clear
        node._updated_threads.clear()
        assert len(node._updated_threads) == 0
