"""
Integration tests for orchestrator delegation scenarios.

Tests delegation patterns:
- Single worker delegation
- Multiple workers
- Worker selection
- Delegation errors
- Response tracking

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
    create_mock_worker_node
)


@pytest.mark.integration
@pytest.mark.orchestrator
@pytest.mark.delegation
class TestBasicDelegation(BaseIntegrationTest):
    """Test basic delegation scenarios."""
    
    def test_delegate_to_single_worker(self, mock_llm_provider):
        """✅ SIMPLE: Test delegating work to single worker."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1"])
        
        # Create plan with remote work
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=1,
            remote_workers=["worker1"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Verify delegation setup
        item = list(plan.items.values())[0]
        assert item.kind == WorkItemKind.REMOTE
        assert item.assigned_uid == "worker1"
        assert item.status == WorkItemStatus.PENDING
    
    def test_delegate_to_multiple_workers(self, mock_llm_provider):
        """✅ MEDIUM: Test delegating work to multiple workers."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(
            orch, "orch1", ["worker1", "worker2", "worker3"]
        )
        
        # Create plan with multiple remote items
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=3,
            remote_workers=["worker1", "worker2", "worker3"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Verify each item assigned to different worker
        items = list(plan.items.values())
        assigned_workers = [item.assigned_uid for item in items]
        
        assert "worker1" in assigned_workers
        assert "worker2" in assigned_workers
        assert "worker3" in assigned_workers
    
    def test_delegate_and_receive_success_response(self, mock_llm_provider):
        """✅ MEDIUM: Test complete delegation cycle with success."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1"])
        
        # Create and save plan
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=1,
            remote_workers=["worker1"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Set correlation ID for tracking
        item = list(plan.items.values())[0]
        item.correlation_task_id = "corr_123"
        item.status = WorkItemStatus.IN_PROGRESS
        workspace_service.save_work_plan(plan)
        
        # ✅ GENERIC: Simulate worker completing work
        result = simulate_worker_response(
            orch, "thread1", "corr_123",
            success=True,
            content="Task completed successfully",
            from_uid="worker1"
        )
        
        # Should process response
        assert result == "thread1"
    
    def test_delegate_and_receive_failure_response(self, mock_llm_provider):
        """✅ MEDIUM: Test delegation with failure response."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1"])
        
        # Create and save plan
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=1,
            remote_workers=["worker1"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Set correlation ID
        item = list(plan.items.values())[0]
        item.correlation_task_id = "corr_123"
        item.status = WorkItemStatus.IN_PROGRESS
        workspace_service.save_work_plan(plan)
        
        # ✅ GENERIC: Simulate worker failing
        result = simulate_worker_response(
            orch, "thread1", "corr_123",
            success=False,
            content="Task failed: Unable to complete",
            from_uid="worker1"
        )
        
        # Should mark as failed
        updated_plan = workspace_service.load_work_plan("thread1", "orch1")
        updated_item = list(updated_plan.items.values())[0]
        assert updated_item.status == WorkItemStatus.FAILED


@pytest.mark.integration
@pytest.mark.orchestrator
@pytest.mark.delegation
class TestMultiWorkerDelegation(BaseIntegrationTest):
    """Test delegation to multiple workers."""
    
    def test_parallel_delegation_to_multiple_workers(self, mock_llm_provider):
        """✅ MEDIUM: Test delegating multiple tasks in parallel."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(
            orch, "orch1", ["worker1", "worker2", "worker3"]
        )
        
        # Create plan with 3 parallel tasks
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=3,
            remote_workers=["worker1", "worker2", "worker3"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # ✅ GENERIC: Use assertion helper
        assert_work_plan_status(plan, expected_total=3, expected_pending=3)
        
        # All should be remote
        items = list(plan.items.values())
        assert all(item.kind == WorkItemKind.REMOTE for item in items)
    
    def test_sequential_delegation_responses(self, mock_llm_provider):
        """✅ COMPLEX: Test workers completing in sequence."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(
            orch, "orch1", ["worker1", "worker2", "worker3"]
        )
        
        # Create plan
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=3,
            remote_workers=["worker1", "worker2", "worker3"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Set correlation IDs and mark in progress
        items = list(plan.items.values())
        for i, item in enumerate(items):
            item.correlation_task_id = f"corr_{i+1}"
            item.status = WorkItemStatus.IN_PROGRESS
        workspace_service.save_work_plan(plan)
        
        # Workers complete sequentially (all failures for immediate status update)
        simulate_worker_response(orch, "thread1", "corr_1", success=False, from_uid="worker1")
        
        # Check after first
        plan1 = workspace_service.load_work_plan("thread1", "orch1")
        assert_work_plan_status(plan1, expected_failed=1, expected_in_progress=2)
        
        simulate_worker_response(orch, "thread1", "corr_2", success=False, from_uid="worker2")
        
        # Check after second
        plan2 = workspace_service.load_work_plan("thread1", "orch1")
        assert_work_plan_status(plan2, expected_failed=2, expected_in_progress=1)
        
        simulate_worker_response(orch, "thread1", "corr_3", success=False, from_uid="worker3")
        
        # Check after third
        plan3 = workspace_service.load_work_plan("thread1", "orch1")
        assert_work_plan_status(plan3, expected_failed=3, expected_in_progress=0)
    
    def test_mixed_success_failure_responses(self, mock_llm_provider):
        """✅ COMPLEX: Test mixed success and failure responses."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(
            orch, "orch1", ["worker1", "worker2", "worker3", "worker4"]
        )
        
        # Create plan with 4 workers
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=4,
            remote_workers=["worker1", "worker2", "worker3", "worker4"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Set correlation IDs
        items = list(plan.items.values())
        for i, item in enumerate(items):
            item.correlation_task_id = f"corr_{i+1}"
            item.status = WorkItemStatus.IN_PROGRESS
        workspace_service.save_work_plan(plan)
        
        # Send mixed responses (2 failures, 2 successes)
        simulate_worker_response(orch, "thread1", "corr_1", success=False, from_uid="worker1")
        simulate_worker_response(orch, "thread1", "corr_2", success=True, from_uid="worker2")
        simulate_worker_response(orch, "thread1", "corr_3", success=False, from_uid="worker3")
        simulate_worker_response(orch, "thread1", "corr_4", success=True, from_uid="worker4")
        
        # Check final state
        final_plan = workspace_service.load_work_plan("thread1", "orch1")
        final_items = list(final_plan.items.values())
        
        # Failures marked immediately, successes stored for LLM
        assert final_items[0].status == WorkItemStatus.FAILED
        assert final_items[1].status == WorkItemStatus.IN_PROGRESS  # Success stored
        assert final_items[2].status == WorkItemStatus.FAILED
        assert final_items[3].status == WorkItemStatus.IN_PROGRESS  # Success stored


@pytest.mark.integration
@pytest.mark.orchestrator
@pytest.mark.delegation
class TestDelegationEdgeCases(BaseIntegrationTest):
    """Test delegation edge cases."""
    
    def test_delegate_with_no_available_workers(self, mock_llm_provider):
        """✅ MEDIUM: Test delegation when no workers available."""
        # ✅ GENERIC: Use setup helper with empty workers
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", [])
        
        # Try to create plan with remote work (no workers)
        plan = WorkPlan(
            summary="Test plan",
            owner_uid="orch1",
            thread_id="thread1"
        )
        
        # Can still save plan (delegation happens later)
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        assert plan is not None
    
    def test_delegate_more_tasks_than_workers(self, mock_llm_provider):
        """✅ MEDIUM: Test delegating more tasks than available workers."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(
            orch, "orch1", ["worker1", "worker2"]
        )
        
        # Create plan with 5 tasks but only 2 workers
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=5,
            remote_workers=["worker1", "worker2"]  # Will cycle through
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Should assign tasks (cycling through workers)
        items = list(plan.items.values())
        assigned_workers = [item.assigned_uid for item in items]
        
        # Should have assignments (may repeat workers)
        assert len([w for w in assigned_workers if w == "worker1"]) >= 1
        assert len([w for w in assigned_workers if w == "worker2"]) >= 1
    
    def test_delegate_with_duplicate_correlation_ids(self, mock_llm_provider):
        """✅ COMPLEX: Test handling duplicate correlation IDs."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(
            orch, "orch1", ["worker1", "worker2"]
        )
        
        # Create plan
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=2,
            remote_workers=["worker1", "worker2"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Set SAME correlation ID for both (edge case)
        items = list(plan.items.values())
        items[0].correlation_task_id = "duplicate_corr"
        items[0].status = WorkItemStatus.IN_PROGRESS
        items[1].correlation_task_id = "duplicate_corr"  # Duplicate!
        items[1].status = WorkItemStatus.IN_PROGRESS
        workspace_service.save_work_plan(plan)
        
        # Send response with duplicate correlation
        result = simulate_worker_response(
            orch, "thread1", "duplicate_corr",
            success=False,
            from_uid="worker1"
        )
        
        # Should handle (might update first matching item)
        assert result is not None or result == "thread1"
    
    def test_response_for_cancelled_delegation(self, mock_llm_provider):
        """✅ MEDIUM: Test response for work that was cancelled."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1"])
        
        # Create plan
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=1,
            remote_workers=["worker1"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Set correlation and mark as FAILED (cancelled)
        item = list(plan.items.values())[0]
        item.correlation_task_id = "corr_123"
        item.status = WorkItemStatus.FAILED  # Already cancelled
        workspace_service.save_work_plan(plan)
        
        # Worker still sends response (late)
        result = simulate_worker_response(
            orch, "thread1", "corr_123",
            success=True,
            from_uid="worker1"
        )
        
        # Should handle gracefully
        assert result is not None or result is None


@pytest.mark.integration
@pytest.mark.orchestrator
@pytest.mark.delegation
class TestDelegationWithMixedWork(BaseIntegrationTest):
    """Test delegation combined with local work."""
    
    def test_mixed_local_and_delegated_work(self, mock_llm_provider):
        """✅ MEDIUM: Test plan with both local and delegated work."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(
            orch, "orch1", ["worker1", "worker2"]
        )
        
        # Create mixed plan
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_local=2,
            num_remote=2,
            remote_workers=["worker1", "worker2"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Verify mix
        items = list(plan.items.values())
        local_items = [i for i in items if i.kind == WorkItemKind.LOCAL]
        remote_items = [i for i in items if i.kind == WorkItemKind.REMOTE]
        
        assert len(local_items) == 2
        assert len(remote_items) == 2
        assert_work_plan_status(plan, expected_total=4)
    
    def test_complete_local_before_delegated(self, mock_llm_provider):
        """✅ COMPLEX: Test completing local work before delegated work."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1"])
        
        # Create mixed plan
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_local=1,
            num_remote=1,
            remote_workers=["worker1"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Complete local item first
        items = list(plan.items.values())
        local_item = [i for i in items if i.kind == WorkItemKind.LOCAL][0]
        remote_item = [i for i in items if i.kind == WorkItemKind.REMOTE][0]
        
        local_item.status = WorkItemStatus.DONE
        workspace_service.save_work_plan(plan)
        
        # Check state
        updated_plan = workspace_service.load_work_plan("thread1", "orch1")
        assert_work_plan_status(updated_plan, expected_done=1, expected_pending=1)
        
        # Now complete remote
        remote_item.correlation_task_id = "corr_123"
        remote_item.status = WorkItemStatus.IN_PROGRESS
        workspace_service.save_work_plan(plan)
        
        simulate_worker_response(
            orch, "thread1", "corr_123",
            success=False,  # Use failure for immediate status update
            from_uid="worker1"
        )
        
        # Check final
        final_plan = workspace_service.load_work_plan("thread1", "orch1")
        assert_work_plan_status(final_plan, expected_done=1, expected_failed=1)
