"""
Infrastructure tests for hierarchical orchestrator setup.

⚠️  INFRASTRUCTURE ONLY - These tests verify setup, NOT real execution:
- Multi-level orchestrator creation
- Hierarchical thread relationships
- Work plan ownership structure
- Thread hierarchy data structures
- Context and state setup for hierarchies

❌ NOT TESTED HERE: Real hierarchical orchestration flows, actual delegation chains
✅ FOR REAL FLOWS: See test_orchestrator_agent_flows.py (will add hierarchical flows later)

✅ GENERIC: Uses shared helpers for multi-node setup
✅ SOLID: Tests infrastructure components for hierarchies
"""

import pytest
from unittest.mock import Mock
from tests.base import (
    BaseIntegrationTest,
    setup_node_with_state,
    setup_node_with_context,
    create_orchestrator_node,
    create_work_plan_with_items,
    create_thread_hierarchy,
    create_multi_level_hierarchy,
    assert_work_plan_status,
    assert_thread_hierarchy,
    assert_response_routes_to_root,
    get_hierarchy_depth,
)
from mas.elements.nodes.common.workload import WorkItemStatus, Task


@pytest.mark.integration
@pytest.mark.multi_node
@pytest.mark.hierarchical
class TestTwoLevelOrchestration(BaseIntegrationTest):
    """Test parent orchestrator delegating to child orchestrator."""
    
    def test_create_parent_and_child_orchestrators(self, mock_llm_provider):
        """✅ SIMPLE: Test creating parent and child orchestrators."""
        # ✅ GENERIC: Use creation helper
        parent_orch = create_orchestrator_node("parent_orch", mock_llm_provider)
        child_orch = create_orchestrator_node("child_orch", mock_llm_provider)
        
        # ✅ GENERIC: Use setup helpers
        parent_state, parent_ctx = setup_node_with_context(parent_orch, "parent_orch", ["child_orch"])
        child_state, child_ctx = setup_node_with_context(child_orch, "child_orch", [])
        
        # Both should be initialized
        assert parent_orch is not None
        assert child_orch is not None
        assert parent_ctx.uid == "parent_orch"
        assert child_ctx.uid == "child_orch"
    
    def test_parent_orchestrator_has_child_in_adjacent_nodes(self, mock_llm_provider):
        """✅ SIMPLE: Test parent sees child in adjacent nodes."""
        parent_orch = create_orchestrator_node("parent_orch", mock_llm_provider)
        parent_state, parent_ctx = setup_node_with_context(parent_orch, "parent_orch", ["child_orch"])
        
        # Parent should see child orchestrator
        assert "child_orch" in list(parent_ctx.adjacent_nodes)
    
    def test_parent_can_delegate_to_child_orchestrator(self, mock_llm_provider):
        """✅ MEDIUM: Test parent creates work plan with child assignment."""
        parent_orch = create_orchestrator_node("parent_orch", mock_llm_provider)
        parent_state, parent_ctx = setup_node_with_context(parent_orch, "parent_orch", ["child_orch"])
        
        # Create work plan with work for child orchestrator
        plan = create_work_plan_with_items(
            "thread1", "parent_orch",
            num_remote=1,
            remote_workers=["child_orch"]
        )
        
        service = parent_orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Work should be assigned to child orchestrator
        item = list(plan.items.values())[0]
        assert item.assigned_uid == "child_orch"
        assert item.status == WorkItemStatus.PENDING
    
    def test_child_orchestrator_can_create_own_work_plan(self, mock_llm_provider):
        """✅ MEDIUM: Test child orchestrator creates its own work plan."""
        parent_orch = create_orchestrator_node("parent_orch", mock_llm_provider)
        child_orch = create_orchestrator_node("child_orch", mock_llm_provider)
        
        parent_state, parent_ctx = setup_node_with_context(parent_orch, "parent_orch", ["child_orch"])
        child_state, child_ctx = setup_node_with_context(child_orch, "child_orch", ["worker1"])
        
        # Parent creates work plan
        parent_plan = create_work_plan_with_items(
            "thread1", "parent_orch",
            num_remote=1,
            remote_workers=["child_orch"]
        )
        
        parent_service = parent_orch.get_workload_service()
        parent_workspace_service = parent_service.get_workspace_service()
        parent_workspace_service.save_work_plan(parent_plan)
        
        # Child creates its own work plan (in same thread)
        child_plan = create_work_plan_with_items(
            "thread1", "child_orch",
            num_remote=1,
            remote_workers=["worker1"]
        )
        
        child_service = child_orch.get_workload_service()
        child_workspace_service = child_service.get_workspace_service()
        child_workspace_service.save_work_plan(child_plan)
        
        # Both work plans should exist independently
        loaded_parent_plan = parent_workspace_service.load_work_plan("thread1", "parent_orch")
        loaded_child_plan = child_workspace_service.load_work_plan("thread1", "child_orch")
        
        assert loaded_parent_plan is not None
        assert loaded_child_plan is not None
        assert loaded_parent_plan.owner_uid == "parent_orch"
        assert loaded_child_plan.owner_uid == "child_orch"
    
    def test_parent_and_child_work_plans_isolated(self, mock_llm_provider):
        """✅ MEDIUM: Test parent and child work plans are isolated."""
        parent_orch = create_orchestrator_node("parent_orch", mock_llm_provider)
        child_orch = create_orchestrator_node("child_orch", mock_llm_provider)
        
        parent_state, parent_ctx = setup_node_with_context(parent_orch, "parent_orch", ["child_orch"])
        child_state, child_ctx = setup_node_with_context(child_orch, "child_orch", [])
        
        # Create different work plans
        parent_plan = create_work_plan_with_items("thread1", "parent_orch", num_local=2)
        child_plan = create_work_plan_with_items("thread1", "child_orch", num_local=3)
        
        parent_service = parent_orch.get_workload_service()
        parent_workspace_service = parent_service.get_workspace_service()
        parent_workspace_service.save_work_plan(parent_plan)
        
        child_service = child_orch.get_workload_service()
        child_workspace_service = child_service.get_workspace_service()
        child_workspace_service.save_work_plan(child_plan)
        
        # Load and verify isolation
        loaded_parent = parent_workspace_service.load_work_plan("thread1", "parent_orch")
        loaded_child = child_workspace_service.load_work_plan("thread1", "child_orch")
        
        assert len(loaded_parent.items) == 2
        assert len(loaded_child.items) == 3


@pytest.mark.integration
@pytest.mark.multi_node
@pytest.mark.hierarchical
class TestThreeLevelOrchestration(BaseIntegrationTest):
    """Test 3-level orchestrator hierarchy."""
    
    def test_three_level_orchestrator_chain(self, mock_llm_provider):
        """✅ MEDIUM: Test grandparent → parent → child orchestrators."""
        # ✅ GENERIC: Use creation helper
        grandparent = create_orchestrator_node("orch_L1", mock_llm_provider)
        parent = create_orchestrator_node("orch_L2", mock_llm_provider)
        child = create_orchestrator_node("orch_L3", mock_llm_provider)
        
        # Setup contexts
        grandparent_state, grandparent_ctx = setup_node_with_context(grandparent, "orch_L1", ["orch_L2"])
        parent_state, parent_ctx = setup_node_with_context(parent, "orch_L2", ["orch_L3"])
        child_state, child_ctx = setup_node_with_context(child, "orch_L3", [])
        
        # Each level should be initialized
        assert grandparent_ctx.uid == "orch_L1"
        assert parent_ctx.uid == "orch_L2"
        assert child_ctx.uid == "orch_L3"
    
    def test_three_level_work_plan_creation(self, mock_llm_provider):
        """✅ COMPLEX: Test each level creates own work plan."""
        grandparent = create_orchestrator_node("orch_L1", mock_llm_provider)
        parent = create_orchestrator_node("orch_L2", mock_llm_provider)
        child = create_orchestrator_node("orch_L3", mock_llm_provider)
        
        grandparent_state, grandparent_ctx = setup_node_with_context(grandparent, "orch_L1", ["orch_L2"])
        parent_state, parent_ctx = setup_node_with_context(parent, "orch_L2", ["orch_L3"])
        child_state, child_ctx = setup_node_with_context(child, "orch_L3", ["worker1"])
        
        # Each level creates work plan
        l1_plan = create_work_plan_with_items("thread1", "orch_L1", num_remote=1, remote_workers=["orch_L2"])
        l2_plan = create_work_plan_with_items("thread1", "orch_L2", num_remote=1, remote_workers=["orch_L3"])
        l3_plan = create_work_plan_with_items("thread1", "orch_L3", num_remote=1, remote_workers=["worker1"])
        
        # Save all plans
        l1_service = grandparent.get_workload_service().get_workspace_service()
        l2_service = parent.get_workload_service().get_workspace_service()
        l3_service = child.get_workload_service().get_workspace_service()
        
        l1_service.save_work_plan(l1_plan)
        l2_service.save_work_plan(l2_plan)
        l3_service.save_work_plan(l3_plan)
        
        # All should exist
        assert l1_service.load_work_plan("thread1", "orch_L1") is not None
        assert l2_service.load_work_plan("thread1", "orch_L2") is not None
        assert l3_service.load_work_plan("thread1", "orch_L3") is not None
    
    def test_four_level_orchestrator_hierarchy(self, mock_llm_provider):
        """✅ COMPLEX: Test 4-level deep orchestrator hierarchy."""
        # Create 4 levels
        orchestrators = [
            create_orchestrator_node(f"orch_L{i}", mock_llm_provider)
            for i in range(1, 5)
        ]
        
        # Setup contexts (each points to next level)
        for i, orch in enumerate(orchestrators[:-1]):
            next_uid = f"orch_L{i+2}"
            setup_node_with_context(orch, f"orch_L{i+1}", [next_uid])
        
        # Last level has worker
        setup_node_with_context(orchestrators[-1], "orch_L4", ["worker1"])
        
        # All should be connected
        for i, orch in enumerate(orchestrators):
            assert hasattr(orch, '_ctx')
            assert orch._ctx.uid == f"orch_L{i+1}"


@pytest.mark.integration
@pytest.mark.multi_node
@pytest.mark.hierarchical
class TestHierarchicalThreadManagement(BaseIntegrationTest):
    """Test thread hierarchy in orchestrator hierarchies."""
    
    def test_thread_hierarchy_with_two_orchestrators(self, mock_llm_provider):
        """✅ MEDIUM: Test thread hierarchy with parent and child orchestrators."""
        parent_orch = create_orchestrator_node("parent_orch", mock_llm_provider)
        child_orch = create_orchestrator_node("child_orch", mock_llm_provider)
        
        parent_state, parent_ctx = setup_node_with_context(parent_orch, "parent_orch", ["child_orch"])
        child_state, child_ctx = setup_node_with_context(child_orch, "child_orch", [])
        
        # ✅ GENERIC: Create thread hierarchy
        hierarchy = create_thread_hierarchy(parent_orch, "parent_thread", num_children=1)
        parent_thread = hierarchy["parent"]
        child_thread = hierarchy["children"][0]
        
        # ✅ GENERIC: Assert hierarchy
        assert_thread_hierarchy(parent_thread, child_thread)
    
    def test_work_plan_in_parent_thread(self, mock_llm_provider):
        """✅ MEDIUM: Test parent orchestrator work plan in root thread."""
        parent_orch = create_orchestrator_node("parent_orch", mock_llm_provider)
        parent_state, parent_ctx = setup_node_with_context(parent_orch, "parent_orch", ["child_orch"])
        
        # Create thread hierarchy
        thread_service = parent_orch.get_workload_service().get_thread_service()
        root_thread = thread_service.create_root_thread(
            title="Root Thread",
            objective="Root objective",
            initiator="parent_orch"
        )
        
        # Create work plan in root thread
        plan = create_work_plan_with_items(
            root_thread.thread_id, "parent_orch",
            num_remote=1,
            remote_workers=["child_orch"]
        )
        
        workspace_service = parent_orch.get_workload_service().get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Work plan should be owned by root thread
        loaded_plan = workspace_service.load_work_plan(root_thread.thread_id, "parent_orch")
        assert loaded_plan is not None
        assert loaded_plan.thread_id == root_thread.thread_id
    
    def test_child_response_routes_to_parent_in_hierarchy(self, mock_llm_provider):
        """✅ COMPLEX: Test child orchestrator response routes to parent thread."""
        parent_orch = create_orchestrator_node("parent_orch", mock_llm_provider)
        child_orch = create_orchestrator_node("child_orch", mock_llm_provider)
        
        parent_state, parent_ctx = setup_node_with_context(parent_orch, "parent_orch", ["child_orch"])
        child_state, child_ctx = setup_node_with_context(child_orch, "child_orch", [])
        
        # Create thread hierarchy
        hierarchy = create_thread_hierarchy(parent_orch, "parent_thread", num_children=1)
        parent_thread = hierarchy["parent"]
        child_thread = hierarchy["children"][0]
        
        # Parent work plan in parent thread
        plan = create_work_plan_with_items(
            parent_thread.thread_id, "parent_orch",
            num_remote=1,
            remote_workers=["child_orch"]
        )
        
        workspace_service = parent_orch.get_workload_service().get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Set correlation
        item = list(plan.items.values())[0]
        item.correlation_task_id = "corr_123"
        item.status = WorkItemStatus.IN_PROGRESS
        workspace_service.save_work_plan(plan)
        
        # Response from child thread should route to parent thread
        response = Task(
            content="Child work completed",
            created_by="child_orch",
            correlation_task_id="corr_123",
            thread_id=child_thread.thread_id,  # Response from child thread
            error="Child work failed"
        )
        
        # Handle response
        result_thread = parent_orch._handle_task_response(response)
        
        # ✅ GENERIC: Assert routing
        assert_response_routes_to_root(parent_orch, child_thread.thread_id, parent_thread.thread_id)
    
    def test_multi_level_thread_hierarchy_depth(self, mock_llm_provider):
        """✅ MEDIUM: Test thread depth in multi-level hierarchy."""
        orch = create_orchestrator_node("orch1", mock_llm_provider)
        orch_state, orch_ctx = setup_node_with_context(orch, "orch1", [])
        
        # ✅ GENERIC: Create multi-level hierarchy
        threads = create_multi_level_hierarchy(orch, levels=4)
        
        thread_service = orch.get_workload_service().get_thread_service()
        
        # ✅ GENERIC: Verify depth at each level
        assert get_hierarchy_depth(thread_service, threads[0].thread_id) == 0  # Root
        assert get_hierarchy_depth(thread_service, threads[1].thread_id) == 1  # Child
        assert get_hierarchy_depth(thread_service, threads[2].thread_id) == 2  # Grandchild
        assert get_hierarchy_depth(thread_service, threads[3].thread_id) == 3  # Great-grandchild


@pytest.mark.integration
@pytest.mark.multi_node
@pytest.mark.hierarchical
class TestHierarchicalWorkPlanOwnership(BaseIntegrationTest):
    """Test work plan ownership in orchestrator hierarchies."""
    
    def test_each_orchestrator_owns_own_work_plan(self, mock_llm_provider):
        """✅ MEDIUM: Test each orchestrator owns its work plan."""
        parent_orch = create_orchestrator_node("parent_orch", mock_llm_provider)
        child_orch = create_orchestrator_node("child_orch", mock_llm_provider)
        
        parent_state, parent_ctx = setup_node_with_context(parent_orch, "parent_orch", ["child_orch"])
        child_state, child_ctx = setup_node_with_context(child_orch, "child_orch", [])
        
        # Create work plans
        parent_plan = create_work_plan_with_items("thread1", "parent_orch", num_local=1)
        child_plan = create_work_plan_with_items("thread1", "child_orch", num_local=1)
        
        parent_service = parent_orch.get_workload_service().get_workspace_service()
        child_service = child_orch.get_workload_service().get_workspace_service()
        
        parent_service.save_work_plan(parent_plan)
        child_service.save_work_plan(child_plan)
        
        # Load by owner
        loaded_parent = parent_service.load_work_plan("thread1", "parent_orch")
        loaded_child = child_service.load_work_plan("thread1", "child_orch")
        
        # Verify ownership
        assert loaded_parent.owner_uid == "parent_orch"
        assert loaded_child.owner_uid == "child_orch"
    
    def test_root_thread_owns_work_plan_in_hierarchy(self, mock_llm_provider):
        """✅ MEDIUM: Test root thread owns work plan despite nested orchestrators."""
        parent_orch = create_orchestrator_node("parent_orch", mock_llm_provider)
        parent_state, parent_ctx = setup_node_with_context(parent_orch, "parent_orch", [])
        
        # Create thread hierarchy
        threads = create_multi_level_hierarchy(parent_orch, levels=3)
        root_thread = threads[0]
        grandchild_thread = threads[2]
        
        # Create work plan in root thread
        plan = create_work_plan_with_items(root_thread.thread_id, "parent_orch", num_local=1)
        
        workspace_service = parent_orch.get_workload_service().get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Work plan owner should be found via root thread
        thread_service = parent_orch.get_workload_service().get_thread_service()
        owner_thread = thread_service.find_work_plan_owner(grandchild_thread.thread_id, "parent_orch")
        
        assert owner_thread == root_thread.thread_id
    
    def test_work_plan_isolation_between_orchestrator_levels(self, mock_llm_provider):
        """✅ COMPLEX: Test work plans isolated between hierarchy levels."""
        level1 = create_orchestrator_node("orch_L1", mock_llm_provider)
        level2 = create_orchestrator_node("orch_L2", mock_llm_provider)
        level3 = create_orchestrator_node("orch_L3", mock_llm_provider)
        
        setup_node_with_context(level1, "orch_L1", ["orch_L2"])
        setup_node_with_context(level2, "orch_L2", ["orch_L3"])
        setup_node_with_context(level3, "orch_L3", [])
        
        # Each creates work plan in same thread but different owner
        l1_plan = create_work_plan_with_items("shared_thread", "orch_L1", num_local=1)
        l2_plan = create_work_plan_with_items("shared_thread", "orch_L2", num_local=2)
        l3_plan = create_work_plan_with_items("shared_thread", "orch_L3", num_local=3)
        
        l1_service = level1.get_workload_service().get_workspace_service()
        l2_service = level2.get_workload_service().get_workspace_service()
        l3_service = level3.get_workload_service().get_workspace_service()
        
        l1_service.save_work_plan(l1_plan)
        l2_service.save_work_plan(l2_plan)
        l3_service.save_work_plan(l3_plan)
        
        # Each level loads only its own work plan
        loaded_l1 = l1_service.load_work_plan("shared_thread", "orch_L1")
        loaded_l2 = l2_service.load_work_plan("shared_thread", "orch_L2")
        loaded_l3 = l3_service.load_work_plan("shared_thread", "orch_L3")
        
        # Verify isolation (different item counts)
        assert len(loaded_l1.items) == 1
        assert len(loaded_l2.items) == 2
        assert len(loaded_l3.items) == 3
