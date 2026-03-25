"""
Integration tests for basic orchestrator workflows.

Tests end-to-end scenarios with minimal complexity:
- Single local task execution
- Single remote task delegation
- Simple work plan creation and completion
- Basic state persistence

✅ GENERIC: Uses shared helpers and fixtures
✅ SOLID: Single responsibility per test
"""

import pytest
from unittest.mock import Mock, patch
from mas.elements.nodes.orchestrator.orchestrator_node import OrchestratorNode
from mas.elements.nodes.common.workload import (
    WorkPlan, WorkItem, WorkItemKind, WorkItemStatus, Task
)
from tests.base import (
    BaseIntegrationTest,
    setup_node_with_state,
    setup_node_with_context,
    create_work_plan_with_items,
    assert_work_plan_status,
    simulate_worker_response,
    get_workspace_from_node
)


@pytest.mark.integration
@pytest.mark.orchestrator
@pytest.mark.workflows
class TestOrchestratorBasicWorkflows(BaseIntegrationTest):
    """Test basic orchestrator workflows end-to-end."""
    
    def test_simple_local_task_workflow(self, mock_llm_provider):
        """✅ SIMPLE: Test orchestrator handles single local task."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", [])
        
        # Create simple work plan with 1 local item
        plan = create_work_plan_with_items("thread1", "orch1", num_local=1)
        
        # Save work plan
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # ✅ GENERIC: Use assertion helper
        assert_work_plan_status(plan, expected_total=1, expected_pending=1)
        
        # Mark as done
        item = list(plan.items.values())[0]
        item.status = WorkItemStatus.DONE
        workspace_service.save_work_plan(plan)
        
        # Verify completion
        loaded_plan = workspace_service.load_work_plan("thread1", "orch1")
        assert loaded_plan.is_complete() is True
    
    def test_simple_remote_task_workflow(self, mock_llm_provider):
        """✅ SIMPLE: Test orchestrator delegates to single worker."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1"])
        
        # Create work plan with 1 remote item
        plan = create_work_plan_with_items(
            "thread1", "orch1", 
            num_remote=1, 
            remote_workers=["worker1"]
        )
        
        # Save work plan
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Verify item assigned
        item = list(plan.items.values())[0]
        assert item.kind == WorkItemKind.REMOTE
        assert item.assigned_uid == "worker1"
        assert item.status == WorkItemStatus.PENDING
    
    def test_work_plan_creation_and_retrieval(self, mock_llm_provider):
        """✅ SIMPLE: Test work plan persists across operations."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", [])
        
        # Create and save work plan
        original_plan = WorkPlan(
            summary="Test plan",
            owner_uid="orch1",
            thread_id="thread1"
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(original_plan)
        
        # Retrieve work plan
        loaded_plan = workspace_service.load_work_plan("thread1", "orch1")
        
        assert loaded_plan is not None
        assert loaded_plan.summary == "Test plan"
        assert loaded_plan.owner_uid == "orch1"
        assert loaded_plan.thread_id == "thread1"
    
    def test_multiple_local_tasks_workflow(self, mock_llm_provider):
        """✅ MEDIUM: Test orchestrator handles multiple local tasks."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", [])
        
        # Create work plan with 3 local items
        plan = create_work_plan_with_items("thread1", "orch1", num_local=3)
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # ✅ GENERIC: Use assertion helper
        assert_work_plan_status(plan, expected_total=3, expected_pending=3)
        
        # Complete them one by one
        items = list(plan.items.values())
        
        # First item done
        items[0].status = WorkItemStatus.DONE
        workspace_service.save_work_plan(plan)
        assert_work_plan_status(plan, expected_done=1, expected_pending=2)
        
        # Second item done
        items[1].status = WorkItemStatus.DONE
        workspace_service.save_work_plan(plan)
        assert_work_plan_status(plan, expected_done=2, expected_pending=1)
        
        # Third item done
        items[2].status = WorkItemStatus.DONE
        workspace_service.save_work_plan(plan)
        assert_work_plan_status(plan, expected_done=3, expected_pending=0)
        
        # Plan should be complete
        assert plan.is_complete() is True
    
    def test_mixed_local_and_remote_workflow(self, mock_llm_provider):
        """✅ MEDIUM: Test orchestrator handles mixed local/remote tasks."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(
            orch, "orch1", ["worker1", "worker2"]
        )
        
        # Create mixed work plan
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_local=2,
            num_remote=2,
            remote_workers=["worker1", "worker2"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # ✅ GENERIC: Use assertion helper
        assert_work_plan_status(plan, expected_total=4, expected_pending=4)
        
        # Verify local and remote items
        local_items = [i for i in plan.items.values() if i.kind == WorkItemKind.LOCAL]
        remote_items = [i for i in plan.items.values() if i.kind == WorkItemKind.REMOTE]
        
        assert len(local_items) == 2
        assert len(remote_items) == 2
        
        # Remote items should be assigned
        for item in remote_items:
            assert item.assigned_uid in ["worker1", "worker2"]
    
    def test_work_plan_state_persistence(self, mock_llm_provider):
        """✅ MEDIUM: Test work plan changes persist correctly."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", [])
        
        # Create initial work plan
        plan = create_work_plan_with_items("thread1", "orch1", num_local=2)
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Modify first item
        first_item = list(plan.items.values())[0]
        first_item.status = WorkItemStatus.IN_PROGRESS
        workspace_service.save_work_plan(plan)
        
        # Load and verify
        loaded_plan = workspace_service.load_work_plan("thread1", "orch1")
        loaded_first_item = list(loaded_plan.items.values())[0]
        assert loaded_first_item.status == WorkItemStatus.IN_PROGRESS
        
        # Modify second item
        second_item = list(plan.items.values())[1]
        second_item.status = WorkItemStatus.DONE
        workspace_service.save_work_plan(plan)
        
        # Load and verify both changes persist
        loaded_plan = workspace_service.load_work_plan("thread1", "orch1")
        items = list(loaded_plan.items.values())
        assert items[0].status == WorkItemStatus.IN_PROGRESS
        assert items[1].status == WorkItemStatus.DONE


@pytest.mark.integration
@pytest.mark.orchestrator
@pytest.mark.workflows
class TestOrchestratorWorkflowCompletion(BaseIntegrationTest):
    """Test work plan completion detection in workflows."""
    
    def test_workflow_completes_when_all_done(self, mock_llm_provider):
        """✅ SIMPLE: Test workflow completes when all items done."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", [])
        
        plan = create_work_plan_with_items("thread1", "orch1", num_local=2)
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Mark all done
        for item in plan.items.values():
            item.status = WorkItemStatus.DONE
        workspace_service.save_work_plan(plan)
        
        assert plan.is_complete() is True
    
    def test_workflow_completes_with_mixed_done_failed(self, mock_llm_provider):
        """✅ MEDIUM: Test workflow completes with some failures."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", [])
        
        plan = create_work_plan_with_items("thread1", "orch1", num_local=3)
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Mixed completion
        items = list(plan.items.values())
        items[0].status = WorkItemStatus.DONE
        items[1].status = WorkItemStatus.FAILED
        items[2].status = WorkItemStatus.DONE
        workspace_service.save_work_plan(plan)
        
        # Should be complete (DONE + FAILED = complete)
        assert plan.is_complete() is True
        assert_work_plan_status(plan, expected_done=2, expected_failed=1)
    
    def test_workflow_not_complete_with_pending(self, mock_llm_provider):
        """✅ SIMPLE: Test workflow not complete with pending items."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", [])
        
        plan = create_work_plan_with_items("thread1", "orch1", num_local=2)
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # One done, one pending
        items = list(plan.items.values())
        items[0].status = WorkItemStatus.DONE
        # items[1] remains PENDING
        workspace_service.save_work_plan(plan)
        
        assert plan.is_complete() is False
    
    def test_workflow_not_complete_with_in_progress(self, mock_llm_provider):
        """✅ SIMPLE: Test workflow not complete with in-progress items."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", [])
        
        plan = create_work_plan_with_items("thread1", "orch1", num_local=2)
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # One done, one in progress
        items = list(plan.items.values())
        items[0].status = WorkItemStatus.DONE
        items[1].status = WorkItemStatus.IN_PROGRESS
        workspace_service.save_work_plan(plan)
        
        assert plan.is_complete() is False
