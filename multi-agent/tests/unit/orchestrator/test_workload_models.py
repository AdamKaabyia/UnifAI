"""
Unit tests for workload models used by orchestrator.

Tests:
- WorkPlan, WorkItem models
- Status transitions
- UnifiedWorkloadService
- WorkspaceService operations
"""

import pytest
from datetime import datetime

from mas.elements.nodes.common.workload import (
    WorkPlan, WorkItem, WorkItemStatus, WorkItemKind,
    UnifiedWorkloadService, InMemoryStorage,
    WorkItemResult, WorkPlanStatus
)


@pytest.mark.unit
@pytest.mark.workload
class TestWorkItemModel:
    """Test WorkItem model."""
    
    def test_work_item_creation(self):
        """Test basic work item creation."""
        item = WorkItem(
            id="item_1",
            kind=WorkItemKind.LOCAL,
            title="Test task",
            description="Do something",
            status=WorkItemStatus.PENDING
        )
        
        assert item.id == "item_1"
        assert item.kind == WorkItemKind.LOCAL
        assert item.status == WorkItemStatus.PENDING
        assert item.retry_count == 0
        assert item.max_retries == 3
    
    def test_work_item_with_remote_execution(self):
        """Test remote execution work item."""
        item = WorkItem(
            id="item_1",
            kind=WorkItemKind.REMOTE,
            title="Remote task",
            description="Delegate this",
            assigned_uid="worker1",
            status=WorkItemStatus.PENDING
        )
        
        assert item.kind == WorkItemKind.REMOTE
        assert item.assigned_uid == "worker1"
    
    def test_work_item_status_transitions(self):
        """Test work item can transition through statuses."""
        item = WorkItem(
            id="item_1",
            kind=WorkItemKind.LOCAL,
            title="Test",
            description="Test",
            status=WorkItemStatus.PENDING
        )
        
        # PENDING → IN_PROGRESS
        item.status = WorkItemStatus.IN_PROGRESS
        assert item.status == WorkItemStatus.IN_PROGRESS
        
        # IN_PROGRESS → DONE
        item.status = WorkItemStatus.DONE
        assert item.status == WorkItemStatus.DONE
    
    def test_work_item_retry_count(self):
        """Test retry count increments."""
        item = WorkItem(
            id="item_1",
            kind=WorkItemKind.REMOTE,
            title="Test",
            description="Test",
            status=WorkItemStatus.IN_PROGRESS
        )
        
        # Simulate failures
        item.retry_count += 1
        assert item.retry_count == 1
        
        item.retry_count += 1
        assert item.retry_count == 2
        
        # Check if max retries reached
        assert item.retry_count < item.max_retries


@pytest.mark.unit
@pytest.mark.workload
class TestWorkPlanModel:
    """Test WorkPlan model."""
    
    def test_work_plan_creation(self):
        """Test basic work plan creation."""
        plan = WorkPlan(
            summary="Test plan",
            owner_uid="orch1",
            thread_id="thread_1"
        )
        
        assert plan.summary == "Test plan"
        assert plan.owner_uid == "orch1"
        assert plan.thread_id == "thread_1"
        assert len(plan.items) == 0
    
    def test_work_plan_add_items(self):
        """Test adding items to work plan."""
        plan = WorkPlan(
            summary="Test plan",
            owner_uid="orch1",
            thread_id="thread_1"
        )
        
        item1 = WorkItem(
            id="item_1",
            kind=WorkItemKind.LOCAL,
            title="Task 1",
            description="First task",
            status=WorkItemStatus.PENDING
        )
        
        item2 = WorkItem(
            id="item_2",
            kind=WorkItemKind.REMOTE,
            title="Task 2",
            description="Second task",
            assigned_to="worker1",
            status=WorkItemStatus.PENDING
        )
        
        plan.items["item_1"] = item1
        plan.items["item_2"] = item2
        
        assert len(plan.items) == 2
        assert "item_1" in plan.items
        assert "item_2" in plan.items
    
    def test_work_plan_get_status_counts(self):
        """Test work plan status counting."""
        plan = WorkPlan(
            summary="Test plan",
            owner_uid="orch1",
            thread_id="thread_1"
        )
        
        # Add items with different statuses
        plan.items["item_1"] = WorkItem(
            id="item_1", kind=WorkItemKind.LOCAL,
            title="T1", description="D1", status=WorkItemStatus.PENDING
        )
        plan.items["item_2"] = WorkItem(
            id="item_2", kind=WorkItemKind.REMOTE,
            title="T2", description="D2", status=WorkItemStatus.IN_PROGRESS
        )
        plan.items["item_3"] = WorkItem(
            id="item_3", kind=WorkItemKind.LOCAL,
            title="T3", description="D3", status=WorkItemStatus.DONE
        )
        
        counts = plan.get_status_counts()
        
        assert counts.pending == 1
        assert counts.in_progress == 1
        assert counts.done == 1
        assert counts.failed == 0
        assert counts.total == 3


@pytest.mark.unit
@pytest.mark.workload
class TestUnifiedWorkloadService:
    """Test UnifiedWorkloadService."""
    
    def test_service_creation_with_in_memory_storage(self):
        """Test creating service with in-memory storage."""
        service = UnifiedWorkloadService.create_in_memory()
        
        assert service is not None
        assert service.get_thread_service() is not None
        assert service.get_workspace_service() is not None
    
    def test_service_can_create_thread(self):
        """Test thread creation through service."""
        service = UnifiedWorkloadService.create_in_memory()
        
        thread = service.create_thread("Test thread", "Test objective", "orch1")
        
        assert thread is not None
        assert thread.title == "Test thread"
        assert thread.objective == "Test objective"
        assert thread.initiator == "orch1"
        assert thread.thread_id is not None
    
    def test_service_can_get_created_thread(self):
        """Test retrieving created thread."""
        service = UnifiedWorkloadService.create_in_memory()
        
        thread = service.create_thread("Test", "Obj", "orch1")
        retrieved = service.get_thread(thread.thread_id)
        
        assert retrieved is not None
        assert retrieved.thread_id == thread.thread_id
        assert retrieved.title == "Test"
    
    def test_service_can_create_and_save_work_plan(self):
        """Test work plan creation and persistence."""
        service = UnifiedWorkloadService.create_in_memory()
        
        # Create thread first
        thread = service.create_thread("Test", "Obj", "orch1")
        
        # Create work plan
        workspace_service = service.get_workspace_service()
        plan = workspace_service.create_work_plan(thread.thread_id, "orch1", "My Plan")
        
        # Add item
        item = WorkItem(
            id="item_1",
            kind=WorkItemKind.LOCAL,
            title="Task",
            description="Do it",
            status=WorkItemStatus.PENDING
        )
        plan.items["item_1"] = item
        
        # Save
        success = workspace_service.save_work_plan(plan)
        assert success is True
        
        # Load
        loaded_plan = workspace_service.load_work_plan(thread.thread_id, "orch1")
        assert loaded_plan is not None
        assert loaded_plan.summary == "My Plan"
        assert "item_1" in loaded_plan.items
    
    def test_service_workspace_operations(self):
        """Test workspace facts and variables."""
        service = UnifiedWorkloadService.create_in_memory()
        
        # Create thread
        thread = service.create_thread("Test", "Obj", "orch1")
        
        # Add facts
        service.add_fact(thread.thread_id, "Fact 1")
        service.add_fact(thread.thread_id, "Fact 2")
        
        # Set variables
        service.set_variable(thread.thread_id, "status", "processing")
        service.set_variable(thread.thread_id, "count", 42)
        
        # Get workspace
        workspace = service.get_workspace(thread.thread_id)
        
        assert len(workspace.context.facts) == 2
        assert "Fact 1" in workspace.context.facts
        assert workspace.context.variables["status"] == "processing"
        assert workspace.context.variables["count"] == 42
    
    def test_service_child_thread_creation(self):
        """Test creating child threads."""
        service = UnifiedWorkloadService.create_in_memory()
        thread_service = service.get_thread_service()
        
        # Create parent
        parent = service.create_thread("Parent", "Obj", "orch1")
        
        # Create child
        child = thread_service.create_child_thread(
            parent, "Child task", "Child objective", "orch1"
        )
        
        assert child is not None
        assert child.parent_thread_id == parent.thread_id
        assert child.title == "Child task"
        assert child.initiator == "orch1"
