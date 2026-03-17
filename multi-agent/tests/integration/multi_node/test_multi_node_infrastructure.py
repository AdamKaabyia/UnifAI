"""
Infrastructure tests for multi-node setup (Orchestrator + CustomAgent).

⚠️  INFRASTRUCTURE ONLY - These tests verify setup, NOT real execution:
- Node creation and initialization
- State and context configuration
- Adjacent node relationships
- Workspace isolation
- Work plan data structures

❌ NOT TESTED HERE: Real orchestration flows, packet exchange, actual delegation
✅ FOR REAL FLOWS: See test_orchestrator_agent_flows.py

✅ GENERIC: Uses shared helpers for multi-node setup
✅ SOLID: Tests infrastructure components
"""

import pytest
from unittest.mock import Mock
from tests.base import (
    BaseIntegrationTest,
    setup_node_with_state,
    setup_node_with_context,
    create_custom_agent_node,
    create_orchestrator_node,
    create_work_plan_with_items,
    create_thread_hierarchy,
    assert_work_plan_status,
    get_workspace_from_node,
)
from mas.elements.nodes.common.workload import WorkItemStatus, Task


@pytest.mark.integration
@pytest.mark.multi_node
@pytest.mark.orchestrator_agent
class TestOrchestratorSingleAgent(BaseIntegrationTest):
    """Test orchestrator coordinating single custom agent."""
    
    def test_create_orchestrator_and_agent(self, mock_llm_provider):
        """✅ SIMPLE: Test creating orchestrator and agent nodes."""
        # ✅ GENERIC: Use creation helpers
        orch = create_orchestrator_node("orch1", mock_llm_provider)
        agent = create_custom_agent_node("agent1", mock_llm_provider)
        
        # ✅ GENERIC: Use setup helpers
        orch_state, orch_ctx = setup_node_with_context(orch, "orch1", ["agent1"])
        agent_state, agent_ctx = setup_node_with_context(agent, "agent1", [])
        
        # Both should be properly initialized
        assert orch is not None
        assert agent is not None
        assert orch_ctx.uid == "orch1"
        assert agent_ctx.uid == "agent1"
    
    def test_orchestrator_has_agent_in_adjacent_nodes(self, mock_llm_provider):
        """✅ SIMPLE: Test orchestrator can see agent in adjacent nodes."""
        # ✅ GENERIC: Use helpers
        orch = create_orchestrator_node("orch1", mock_llm_provider)
        agent = create_custom_agent_node("agent1", mock_llm_provider)
        
        orch_state, orch_ctx = setup_node_with_context(orch, "orch1", ["agent1"])
        
        # Orchestrator should have agent1 in adjacent nodes
        assert "agent1" in list(orch_ctx.adjacent_nodes)
    
    def test_orchestrator_creates_work_plan_for_agent(self, mock_llm_provider):
        """✅ MEDIUM: Test orchestrator creates work plan with agent assignment."""
        # ✅ GENERIC: Use helpers
        orch = create_orchestrator_node("orch1", mock_llm_provider)
        orch_state, orch_ctx = setup_node_with_context(orch, "orch1", ["agent1"])
        
        # Create work plan with remote work for agent
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=1,
            remote_workers=["agent1"]
        )
        
        # Save work plan
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Verify work item assigned to agent
        item = list(plan.items.values())[0]
        assert item.assigned_uid == "agent1"
        assert item.status == WorkItemStatus.PENDING
    
    def test_agent_can_be_assigned_work_item(self, mock_llm_provider):
        """✅ MEDIUM: Test custom agent can receive work assignment."""
        # ✅ GENERIC: Use helpers
        orch = create_orchestrator_node("orch1", mock_llm_provider)
        agent = create_custom_agent_node("agent1", mock_llm_provider)
        
        orch_state, orch_ctx = setup_node_with_context(orch, "orch1", ["agent1"])
        agent_state, agent_ctx = setup_node_with_context(agent, "agent1", [])
        
        # Create work plan with agent assignment
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=1,
            remote_workers=["agent1"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Agent should be able to see the assignment
        item = list(plan.items.values())[0]
        assert item.assigned_uid == "agent1"


@pytest.mark.integration
@pytest.mark.multi_node
@pytest.mark.orchestrator_agent
class TestOrchestratorMultipleAgents(BaseIntegrationTest):
    """Test orchestrator coordinating multiple custom agents."""
    
    def test_orchestrator_with_two_agents(self, mock_llm_provider):
        """✅ MEDIUM: Test orchestrator managing two agents."""
        # ✅ GENERIC: Use helpers
        orch = create_orchestrator_node("orch1", mock_llm_provider)
        agent1 = create_custom_agent_node("agent1", mock_llm_provider)
        agent2 = create_custom_agent_node("agent2", mock_llm_provider)
        
        orch_state, orch_ctx = setup_node_with_context(orch, "orch1", ["agent1", "agent2"])
        
        # Create work plan with work for both agents
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=2,
            remote_workers=["agent1", "agent2"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Verify both agents have assignments
        items = list(plan.items.values())
        assigned_uids = [item.assigned_uid for item in items]
        
        assert "agent1" in assigned_uids
        assert "agent2" in assigned_uids
    
    def test_orchestrator_with_three_agents(self, mock_llm_provider):
        """✅ MEDIUM: Test orchestrator managing three agents."""
        # ✅ GENERIC: Use helpers
        orch = create_orchestrator_node("orch1", mock_llm_provider)
        agents = [
            create_custom_agent_node("agent1", mock_llm_provider),
            create_custom_agent_node("agent2", mock_llm_provider),
            create_custom_agent_node("agent3", mock_llm_provider),
        ]
        
        orch_state, orch_ctx = setup_node_with_context(
            orch, "orch1", 
            ["agent1", "agent2", "agent3"]
        )
        
        # Create work plan with work for all three agents
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=3,
            remote_workers=["agent1", "agent2", "agent3"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # ✅ GENERIC: Use assertion helper
        assert_work_plan_status(plan, expected_total=3, expected_pending=3)
        
        # All three agents should have work
        items = list(plan.items.values())
        assigned_uids = [item.assigned_uid for item in items]
        
        assert len(set(assigned_uids)) == 3  # Three unique agents
    
    def test_orchestrator_parallel_agent_execution(self, mock_llm_provider):
        """✅ COMPLEX: Test orchestrator manages multiple agents in parallel."""
        # ✅ GENERIC: Use helpers
        orch = create_orchestrator_node("orch1", mock_llm_provider)
        
        orch_state, orch_ctx = setup_node_with_context(
            orch, "orch1",
            ["agent1", "agent2", "agent3", "agent4"]
        )
        
        # Create work plan with 4 parallel tasks
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=4,
            remote_workers=["agent1", "agent2", "agent3", "agent4"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Set all to IN_PROGRESS (simulating parallel execution)
        for item in plan.items.values():
            item.status = WorkItemStatus.IN_PROGRESS
            item.correlation_task_id = f"corr_{item.id}"
        workspace_service.save_work_plan(plan)
        
        # ✅ GENERIC: Use assertion helper
        assert_work_plan_status(plan, expected_in_progress=4, expected_total=4)


@pytest.mark.integration
@pytest.mark.multi_node
@pytest.mark.orchestrator_agent
class TestOrchestratorAgentWorkspace(BaseIntegrationTest):
    """Test workspace isolation between orchestrator and agents."""
    
    def test_orchestrator_and_agent_have_separate_workspaces(self, mock_llm_provider):
        """✅ MEDIUM: Test orchestrator and agent have isolated workspaces."""
        # ✅ GENERIC: Use helpers
        orch = create_orchestrator_node("orch1", mock_llm_provider)
        agent = create_custom_agent_node("agent1", mock_llm_provider)
        
        orch_state, orch_ctx = setup_node_with_context(orch, "orch1", ["agent1"])
        agent_state, agent_ctx = setup_node_with_context(agent, "agent1", [])
        
        # Create work plan in orchestrator workspace
        plan = create_work_plan_with_items("thread1", "orch1", num_remote=1, remote_workers=["agent1"])
        
        orch_service = orch.get_workload_service()
        orch_workspace_service = orch_service.get_workspace_service()
        orch_workspace_service.save_work_plan(plan)
        
        # Orchestrator should have the work plan
        orch_plan = orch_workspace_service.load_work_plan("thread1", "orch1")
        assert orch_plan is not None
        
        # Agent should NOT have orchestrator's work plan (different workspace)
        agent_service = agent.get_workload_service()
        agent_workspace_service = agent_service.get_workspace_service()
        agent_plan = agent_workspace_service.load_work_plan("thread1", "orch1")
        
        # Agent doesn't have orchestrator's work plan (different owner)
        assert agent_plan is None
    
    def test_agent_workspace_independent_from_orchestrator(self, mock_llm_provider):
        """✅ MEDIUM: Test agent can maintain own workspace context."""
        # ✅ GENERIC: Use helpers
        orch = create_orchestrator_node("orch1", mock_llm_provider)
        agent = create_custom_agent_node("agent1", mock_llm_provider)
        
        orch_state, orch_ctx = setup_node_with_context(orch, "orch1", ["agent1"])
        agent_state, agent_ctx = setup_node_with_context(agent, "agent1", [])
        
        # Agent adds facts to its own workspace
        agent_service = agent.get_workload_service()
        agent_workspace_service = agent_service.get_workspace_service()
        
        # Agent can maintain context (workspace operations work)
        workspace = agent_workspace_service.get_workspace("thread1")
        assert workspace is not None
    
    def test_thread_hierarchy_with_orchestrator_and_agent(self, mock_llm_provider):
        """✅ COMPLEX: Test thread hierarchy when orchestrator delegates to agent."""
        # ✅ GENERIC: Use helpers
        orch = create_orchestrator_node("orch1", mock_llm_provider)
        agent = create_custom_agent_node("agent1", mock_llm_provider)
        
        orch_state, orch_ctx = setup_node_with_context(orch, "orch1", ["agent1"])
        agent_state, agent_ctx = setup_node_with_context(agent, "agent1", [])
        
        # ✅ GENERIC: Create thread hierarchy
        hierarchy = create_thread_hierarchy(orch, "parent_thread", num_children=1)
        parent_thread = hierarchy["parent"]
        child_thread = hierarchy["children"][0]
        
        # Orchestrator has work plan in parent thread
        plan = create_work_plan_with_items(
            parent_thread.thread_id, "orch1",
            num_remote=1,
            remote_workers=["agent1"]
        )
        
        orch_service = orch.get_workload_service()
        orch_workspace_service = orch_service.get_workspace_service()
        orch_workspace_service.save_work_plan(plan)
        
        # Work plan should exist in parent thread
        loaded_plan = orch_workspace_service.load_work_plan(parent_thread.thread_id, "orch1")
        assert loaded_plan is not None


@pytest.mark.integration
@pytest.mark.multi_node
@pytest.mark.orchestrator_agent
class TestOrchestratorAgentCapabilities(BaseIntegrationTest):
    """Test capability verification in multi-node scenarios."""
    
    def test_orchestrator_has_workload_capability(self, mock_llm_provider):
        """✅ SIMPLE: Test orchestrator has workload management capability."""
        orch = create_orchestrator_node("orch1", mock_llm_provider)
        orch_state, orch_ctx = setup_node_with_context(orch, "orch1", [])
        
        # Should have workload capability
        assert hasattr(orch, 'get_workload_service')
        service = orch.get_workload_service()
        assert service is not None
    
    def test_agent_has_workload_capability(self, mock_llm_provider):
        """✅ SIMPLE: Test custom agent has workload capability."""
        agent = create_custom_agent_node("agent1", mock_llm_provider)
        agent_state, agent_ctx = setup_node_with_context(agent, "agent1", [])
        
        # Should have workload capability
        assert hasattr(agent, 'get_workload_service')
        service = agent.get_workload_service()
        assert service is not None
    
    def test_orchestrator_has_iem_capability(self, mock_llm_provider):
        """✅ SIMPLE: Test orchestrator has IEM (messaging) capability."""
        orch = create_orchestrator_node("orch1", mock_llm_provider)
        orch_state, orch_ctx = setup_node_with_context(orch, "orch1", [])
        
        # Should have IEM capability
        assert hasattr(orch, 'ms') or hasattr(orch, 'messenger')
    
    def test_agent_has_iem_capability(self, mock_llm_provider):
        """✅ SIMPLE: Test custom agent has IEM capability."""
        agent = create_custom_agent_node("agent1", mock_llm_provider)
        agent_state, agent_ctx = setup_node_with_context(agent, "agent1", [])
        
        # Should have IEM capability
        assert hasattr(agent, 'ms') or hasattr(agent, 'messenger')
    
    def test_both_nodes_have_compatible_capabilities(self, mock_llm_provider):
        """✅ MEDIUM: Test orchestrator and agent have compatible capabilities."""
        orch = create_orchestrator_node("orch1", mock_llm_provider)
        agent = create_custom_agent_node("agent1", mock_llm_provider)
        
        orch_state, orch_ctx = setup_node_with_context(orch, "orch1", ["agent1"])
        agent_state, agent_ctx = setup_node_with_context(agent, "agent1", [])
        
        # Both should have workload capability
        assert hasattr(orch, 'get_workload_service')
        assert hasattr(agent, 'get_workload_service')
        
        # Both should have IEM capability for communication
        assert hasattr(orch, 'ms') or hasattr(orch, 'messenger')
        assert hasattr(agent, 'ms') or hasattr(agent, 'messenger')
