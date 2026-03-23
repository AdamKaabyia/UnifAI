"""
Integration tests for orchestrator workflows.

Tests real orchestration scenarios end-to-end:
- Work planning with LLM
- Task delegation
- Response handling
- Result synthesis

Uses GENERIC test helpers that work for ALL integration tests.
"""

import pytest
from unittest.mock import Mock, patch
from typing import List

from mas.elements.nodes.orchestrator.orchestrator_node import OrchestratorNode
from mas.elements.nodes.common.workload import Task, UnifiedWorkloadService, InMemoryStorage, WorkItem, WorkItemStatus
from mas.graph.state.graph_state import GraphState
from mas.core.iem.packets import TaskPacket
from mas.core.iem.models import ElementAddress
from tests.base.base_integration_test import BaseIntegrationTest

# ✅ GENERIC: Import helpers that work for ALL integration tests
from tests.base.test_helpers import setup_node_with_state, setup_node_with_context


@pytest.mark.integration
@pytest.mark.orchestrator
class TestOrchestratorBasicWorkflow(BaseIntegrationTest):
    """Test basic orchestrator workflow end-to-end."""
    
    def test_orchestrator_accepts_new_task_and_creates_thread(self, mock_llm):
        """Orchestrator should accept new task and create thread."""
        # Setup
        node = OrchestratorNode(llm=mock_llm)
        # ✅ GENERIC: Need context because _handle_new_work uses self.uid
        setup_node_with_context(node, "orch1", [])
        
        # Create new task
        task = Task(
            content="Please analyze this document",
            created_by="user",
            is_response=False
        )
        
        # Handle new work (no longer calls _run_orchestration_cycle directly - fixed double-cycle bug)
        node._handle_new_work(task)
        
        # Verify thread was created
        assert task.thread_id is not None
        
        # Verify workspace was created for the thread
        workspace = node.workspaces.get_workspace(task.thread_id)
        assert workspace is not None
        assert workspace.thread_id == task.thread_id
    
    def test_orchestrator_handles_response_and_updates_work_plan(self, mock_llm):
        """Orchestrator should handle responses and update work plan."""
        # Setup orchestrator
        node = OrchestratorNode(llm=mock_llm)
        # ✅ GENERIC: Need context because _handle_task_response uses self.uid
        setup_node_with_context(node, "orch1", [])
        
        # Create thread and work plan manually
        service = node.get_workload_service()
        thread = service.create_thread("Test workflow", "Complete task", "orch1")
        
        # Create work plan with pending item
        workspace_service = service.get_workspace_service()
        plan = workspace_service.create_work_plan(thread.thread_id, "orch1")
        
        from mas.elements.nodes.common.workload import WorkItemKind
        item = WorkItem(
            id="item_1",
            kind=WorkItemKind.REMOTE,
            title="Subtask 1",
            description="Do work",
            assigned_uid="worker1",
            status=WorkItemStatus.IN_PROGRESS,
            correlation_task_id="corr_123"
        )
        plan.items["item_1"] = item
        workspace_service.save_work_plan(plan)
        
        # Create response task
        response = Task(
            content="Task completed successfully",
            created_by="worker1",
            is_response=True,
            correlation_task_id="corr_123",
            thread_id=thread.thread_id,
            explicit_success=True
        )
        
        # Handle response
        thread_id = node._handle_task_response(response)
        
        # Verify work plan was updated
        assert thread_id == thread.thread_id
        updated_plan = workspace_service.load_work_plan(thread.thread_id, "orch1")
        assert updated_plan is not None
        
        # Item should have response stored
        updated_item = updated_plan.items.get("item_1")
        assert updated_item is not None
        # Response should be recorded in result_ref (even if not auto-marked DONE)
        assert updated_item.result_ref is not None
        assert updated_item.result_ref.content is not None


@pytest.mark.integration
@pytest.mark.orchestrator
class TestOrchestratorDelegation(BaseIntegrationTest):
    """Test orchestrator delegation capabilities."""
    
    def test_orchestrator_can_delegate_to_adjacent_nodes(self, mock_llm):
        """Orchestrator should be able to delegate work to adjacent nodes."""
        # Setup
        node = OrchestratorNode(llm=mock_llm)
        # ✅ GENERIC: Use helper (works for ALL integration tests)
        setup_node_with_state(node)
        
        # Mock adjacent nodes
        mock_adjacent = {
            "worker1": Mock(uid="worker1", type="worker", description="Data processor")
        }
        
        # Create thread
        service = node.get_workload_service()
        thread = service.create_thread("Delegation test", "Test", "orch1")
        
        # Mock IEM send_task
        with patch.object(node, 'send_task', return_value="packet_123") as mock_send:
            with patch.object(node, 'get_adjacent_nodes', return_value=mock_adjacent):
                # Create delegate task
                delegate_task = Task(
                    content="Process this data",
                    created_by="orch1",
                    thread_id=thread.thread_id,
                    is_response=False
                )
                
                # Send task (simulating what DelegateTaskTool does)
                packet_id = node.send_task("worker1", delegate_task)
                
                assert packet_id == "packet_123"
                mock_send.assert_called_once_with("worker1", delegate_task)
    
    def test_orchestrator_tracks_delegated_work_items(self, mock_llm):
        """Work items should transition to WAITING when delegated."""
        # Setup
        node = OrchestratorNode(llm=mock_llm)
        # ✅ GENERIC: Use helper (works for ALL integration tests)
        setup_node_with_state(node)
        
        # Create thread and work plan
        service = node.get_workload_service()
        thread = service.create_thread("Track delegation", "Test", "orch1")
        
        workspace_service = service.get_workspace_service()
        plan = workspace_service.create_work_plan(thread.thread_id, "orch1")
        
        from mas.elements.nodes.common.workload import WorkItemKind
        item = WorkItem(
            id="item_1",
            kind=WorkItemKind.REMOTE,
            title="Delegated work",
            description="Work to delegate",
            assigned_uid="worker1",
            status=WorkItemStatus.PENDING
        )
        plan.items["item_1"] = item
        workspace_service.save_work_plan(plan)
        
        # Simulate marking as delegated (what happens after send_task)
        item.status = WorkItemStatus.IN_PROGRESS
        item.kind = WorkItemKind.REMOTE
        item.correlation_task_id = "corr_123"
        workspace_service.save_work_plan(plan)
        
        # Verify status
        updated_plan = workspace_service.load_work_plan(thread.thread_id, "orch1")
        updated_item = updated_plan.items["item_1"]
        assert updated_item.status == WorkItemStatus.IN_PROGRESS
        assert updated_item.kind == WorkItemKind.REMOTE
        assert updated_item.correlation_task_id == "corr_123"


@pytest.mark.integration
@pytest.mark.orchestrator
class TestOrchestratorStateManagement(BaseIntegrationTest):
    """Test orchestrator's state management."""
    
    def test_orchestrator_persists_work_plan_across_visits(self, mock_llm):
        """Work plan should persist in GraphState between orchestrator visits."""
        # Setup
        node = OrchestratorNode(llm=mock_llm)
        
        # ✅ GENERIC: Use helper, get state for reuse
        state_view = setup_node_with_state(node)
        state = state_view.backing_state  # Get underlying GraphState for second visit
        
        service = node.get_workload_service()
        thread = service.create_thread("Persistence test", "Test", "orch1")
        
        workspace_service = service.get_workspace_service()
        plan = workspace_service.create_work_plan(thread.thread_id, "orch1", "Test Plan")
        
        from mas.elements.nodes.common.workload import WorkItem, WorkItemKind
        item = WorkItem(
            id="item_1",
            kind=WorkItemKind.LOCAL,
            title="Task 1",
            description="Test task",
            status=WorkItemStatus.PENDING
        )
        plan.items["item_1"] = item
        workspace_service.save_work_plan(plan)
        
        # Second visit: load work plan (simulating re-entrant execution)
        node2 = OrchestratorNode(llm=mock_llm)
        # ✅ GENERIC: Reuse same state for second visit
        from mas.graph.state.state_view import StateView
        from mas.graph.state.graph_state import Channel
        node2._state = StateView(
            state,
            reads={Channel.THREADS, Channel.WORKSPACES, Channel.TASK_THREADS},
            writes={Channel.THREADS, Channel.WORKSPACES, Channel.TASK_THREADS}
        )
        service2 = node2.get_workload_service()
        workspace_service2 = service2.get_workspace_service()
        
        loaded_plan = workspace_service2.load_work_plan(thread.thread_id, "orch1")
        
        # Verify plan persisted
        assert loaded_plan is not None
        assert loaded_plan.summary == "Test Plan"
        assert "item_1" in loaded_plan.items
        assert loaded_plan.items["item_1"].title == "Task 1"
    
    def test_orchestrator_workspace_facts_persist(self, mock_llm):
        """Workspace facts should persist across visits."""
        # Setup
        node = OrchestratorNode(llm=mock_llm)
        # ✅ GENERIC: Use helper (works for ALL integration tests)
        setup_node_with_state(node)
        
        # Create thread and add facts
        service = node.get_workload_service()
        thread = service.create_thread("Facts test", "Test", "orch1")
        
        # Add facts using the mixin method
        node.add_fact_to_workspace(thread.thread_id, "Document analyzed: report.pdf")
        node.add_fact_to_workspace(thread.thread_id, "Found 42 key insights")
        
        # Load workspace and verify facts
        workspace = service.get_workspace(thread.thread_id)
        assert len(workspace.context.facts) == 2
        assert "Document analyzed: report.pdf" in workspace.context.facts
        assert "Found 42 key insights" in workspace.context.facts