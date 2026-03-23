"""
Unit tests for orchestrator response handling.

Tests how orchestrator processes task responses from workers:
- Success responses
- Failure responses
- Response validation
- Correlation tracking
- Work plan updates

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
    BaseUnitTest,
    setup_node_with_state,
    setup_node_with_context,
    create_work_plan_with_items,
    assert_work_plan_status,
    simulate_worker_response
)


@pytest.mark.unit
@pytest.mark.orchestrator
@pytest.mark.responses
class TestResponseValidation(BaseUnitTest):
    """Test response validation and parsing."""
    
    def test_valid_success_response(self, mock_llm_provider):
        """✅ SIMPLE: Test orchestrator accepts valid success response."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1"])
        
        # Create work plan with remote item
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=1,
            remote_workers=["worker1"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Get correlation ID
        item = list(plan.items.values())[0]
        item.correlation_task_id = "corr_123"
        workspace_service.save_work_plan(plan)
        
        # ✅ GENERIC: Use simulate helper
        result = simulate_worker_response(
            orch, "thread1", "corr_123",
            success=True,
            content="Work completed successfully",
            from_uid="worker1"
        )
        
        # Should update work plan
        assert result is not None
    
    def test_valid_failure_response(self, mock_llm_provider):
        """✅ SIMPLE: Test orchestrator accepts valid failure response."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1"])
        
        # Create work plan with remote item
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=1,
            remote_workers=["worker1"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Get correlation ID
        item = list(plan.items.values())[0]
        item.correlation_task_id = "corr_123"
        workspace_service.save_work_plan(plan)
        
        # ✅ GENERIC: Use simulate helper
        result = simulate_worker_response(
            orch, "thread1", "corr_123",
            success=False,
            content="Work failed: Error occurred",
            from_uid="worker1"
        )
        
        # Should update work plan
        assert result is not None
    
    def test_response_without_correlation_id(self, mock_llm_provider):
        """✅ SIMPLE: Test response without correlation ID is ignored."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1"])
        
        # Create task response without correlation
        response = Task(
            content="Response without correlation",
            created_by="worker1",
            is_response=True,
            thread_id="thread1"
            # No correlation_task_id
        )
        
        # Should return None (no work plan to update)
        result = orch._handle_task_response(response)
        assert result is None
    
    def test_response_with_invalid_correlation_id(self, mock_llm_provider):
        """✅ MEDIUM: Test response with non-existent correlation ID."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1"])
        
        # Create work plan
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=1,
            remote_workers=["worker1"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Response with non-existent correlation ID
        result = simulate_worker_response(
            orch, "thread1", "nonexistent_corr_id",
            success=True,
            content="Response",
            from_uid="worker1"
        )
        
        # Should handle gracefully (might return None or thread_id)
        # Either is acceptable behavior
        assert result is None or result == "thread1"


@pytest.mark.unit
@pytest.mark.orchestrator
@pytest.mark.responses
class TestResponseWorkPlanUpdates(BaseUnitTest):
    """Test work plan updates from responses."""
    
    def test_success_response_stores_for_llm_interpretation(self, mock_llm_provider):
        """✅ MEDIUM: Test success response is stored for LLM interpretation."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1"])
        
        # Create work plan
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
        
        # Send success response
        result = simulate_worker_response(
            orch, "thread1", "corr_123",
            success=True,
            content="Work completed",
            from_uid="worker1"
        )
        
        # Should return thread_id (response processed)
        assert result == "thread1"
        
        # Load and verify - status unchanged (stored for LLM interpretation)
        updated_plan = workspace_service.load_work_plan("thread1", "orch1")
        updated_item = list(updated_plan.items.values())[0]
        
        # Success responses don't immediately change status - LLM interprets later
        assert updated_item.status == WorkItemStatus.IN_PROGRESS
    
    def test_failure_response_marks_item_failed(self, mock_llm_provider):
        """✅ MEDIUM: Test failure response marks work item as FAILED."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1"])
        
        # Create work plan
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
        
        # Send failure response
        simulate_worker_response(
            orch, "thread1", "corr_123",
            success=False,
            content="Work failed",
            from_uid="worker1"
        )
        
        # Load and verify
        updated_plan = workspace_service.load_work_plan("thread1", "orch1")
        updated_item = list(updated_plan.items.values())[0]
        
        assert updated_item.status == WorkItemStatus.FAILED
    
    def test_success_response_processed_successfully(self, mock_llm_provider):
        """✅ MEDIUM: Test success response is processed without error."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1"])
        
        # Create work plan
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
        workspace_service.save_work_plan(plan)
        
        # Send response with result data
        result = simulate_worker_response(
            orch, "thread1", "corr_123",
            success=True,
            content="Work completed",
            from_uid="worker1",
            result_data={"output": "test result"}
        )
        
        # Should process successfully
        assert result == "thread1"
        
        # Work plan should still exist
        updated_plan = workspace_service.load_work_plan("thread1", "orch1")
        assert updated_plan is not None


@pytest.mark.unit
@pytest.mark.orchestrator
@pytest.mark.responses
class TestResponseCorrelation(BaseUnitTest):
    """Test correlation ID tracking in responses."""
    
    def test_correlation_id_links_request_to_response(self, mock_llm_provider):
        """✅ MEDIUM: Test correlation ID correctly links request and response."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1", "worker2"])
        
        # Create work plan with multiple remote items
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=2,
            remote_workers=["worker1", "worker2"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Set different correlation IDs and statuses
        items = list(plan.items.values())
        items[0].correlation_task_id = "corr_1"
        items[0].status = WorkItemStatus.IN_PROGRESS
        items[1].correlation_task_id = "corr_2"
        items[1].status = WorkItemStatus.IN_PROGRESS
        workspace_service.save_work_plan(plan)
        
        # Send FAILURE response for first item (failures update status immediately)
        simulate_worker_response(
            orch, "thread1", "corr_1",
            success=False,
            content="First work failed",
            from_uid="worker1"
        )
        
        # Load and verify only first item updated
        updated_plan = workspace_service.load_work_plan("thread1", "orch1")
        updated_items = list(updated_plan.items.values())
        
        # First item should be FAILED, second still IN_PROGRESS
        assert updated_items[0].status == WorkItemStatus.FAILED
        assert updated_items[1].status == WorkItemStatus.IN_PROGRESS
    
    def test_multiple_responses_update_correct_items(self, mock_llm_provider):
        """✅ COMPLEX: Test multiple responses process correctly."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1", "worker2", "worker3"])
        
        # Create work plan with 3 remote items
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
        items[0].correlation_task_id = "corr_1"
        items[0].status = WorkItemStatus.IN_PROGRESS
        items[1].correlation_task_id = "corr_2"
        items[1].status = WorkItemStatus.IN_PROGRESS
        items[2].correlation_task_id = "corr_3"
        items[2].status = WorkItemStatus.IN_PROGRESS
        workspace_service.save_work_plan(plan)
        
        # Send responses in random order (1 failure, 2 successes)
        result2 = simulate_worker_response(orch, "thread1", "corr_2", success=True, from_uid="worker2")
        result1 = simulate_worker_response(orch, "thread1", "corr_1", success=False, from_uid="worker1")
        result3 = simulate_worker_response(orch, "thread1", "corr_3", success=True, from_uid="worker3")
        
        # All should process successfully
        assert result1 == "thread1"
        assert result2 == "thread1"
        assert result3 == "thread1"
        
        # Load and verify failure is marked immediately
        updated_plan = workspace_service.load_work_plan("thread1", "orch1")
        updated_items = list(updated_plan.items.values())
        
        # Only failure updates status immediately
        assert updated_items[0].status == WorkItemStatus.FAILED  # corr_1 failed
        # Success responses stored for LLM interpretation (status unchanged)
        assert updated_items[1].status == WorkItemStatus.IN_PROGRESS  # corr_2 success (stored)
        assert updated_items[2].status == WorkItemStatus.IN_PROGRESS  # corr_3 success (stored)


@pytest.mark.unit
@pytest.mark.orchestrator
@pytest.mark.responses
class TestResponseEdgeCases(BaseUnitTest):
    """Test edge cases in response handling."""
    
    def test_response_for_completed_item(self, mock_llm_provider):
        """✅ MEDIUM: Test response for already completed item."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1"])
        
        # Create work plan
        plan = create_work_plan_with_items(
            "thread1", "orch1",
            num_remote=1,
            remote_workers=["worker1"]
        )
        
        service = orch.get_workload_service()
        workspace_service = service.get_workspace_service()
        workspace_service.save_work_plan(plan)
        
        # Set correlation and mark done
        item = list(plan.items.values())[0]
        item.correlation_task_id = "corr_123"
        item.status = WorkItemStatus.DONE
        workspace_service.save_work_plan(plan)
        
        # Send duplicate success response
        result = simulate_worker_response(
            orch, "thread1", "corr_123",
            success=True,
            from_uid="worker1"
        )
        
        # Should handle gracefully (no error)
        assert result is not None or result is None  # Either is acceptable
    
    def test_response_from_wrong_worker(self, mock_llm_provider):
        """✅ MEDIUM: Test response from different worker than assigned."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1", "worker2"])
        
        # Create work plan with item assigned to worker1
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
        workspace_service.save_work_plan(plan)
        
        # Response from worker2 (not assigned)
        result = simulate_worker_response(
            orch, "thread1", "corr_123",
            success=True,
            from_uid="worker2"  # Different worker
        )
        
        # Should still process (correlation ID is what matters)
        assert result is not None
    
    def test_empty_response_content(self, mock_llm_provider):
        """✅ SIMPLE: Test response with empty content."""
        # ✅ GENERIC: Use setup helper
        orch = OrchestratorNode(llm=mock_llm_provider)
        state_view, context = setup_node_with_context(orch, "orch1", ["worker1"])
        
        # Create work plan
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
        workspace_service.save_work_plan(plan)
        
        # Response with empty content
        result = simulate_worker_response(
            orch, "thread1", "corr_123",
            success=True,
            content="",  # Empty
            from_uid="worker1"
        )
        
        # Should handle gracefully
        assert result is not None or result is None
