"""
Factory for creating WorkPlan and WorkItem objects.

Provides factory methods to create work plans with various configurations
for testing orchestration scenarios.
"""

from typing import List, Dict, Any, Optional
import uuid

from mas.elements.nodes.common.workload import (
    WorkPlan, WorkItem, WorkItemStatus, WorkItemKind,
    WorkItemResult, ToolArguments
)


class WorkPlanFactory:
    """
    Factory for creating WorkPlan and WorkItem objects.
    
    Provides static methods to create work plans with common configurations
    for testing orchestration workflows.
    """
    
    @staticmethod
    def create_work_item(
        id: str = None,
        title: str = "Test Work Item",
        description: str = "A test work item",
        dependencies: List[str] = None,
        status: WorkItemStatus = WorkItemStatus.PENDING,
        kind: WorkItemKind = WorkItemKind.REMOTE,
        assigned_uid: str = None,
        **kwargs
    ) -> WorkItem:
        """
        Create a single WorkItem for testing.
        
        Args:
            id: Item ID (generates one if not provided)
            title: Item title
            description: Item description
            dependencies: List of dependency item IDs
            status: Item status
            kind: Item kind (LOCAL or REMOTE)
            assigned_uid: UID of assigned node (for REMOTE items)
            **kwargs: Additional WorkItem arguments
            
        Returns:
            WorkItem instance
        """
        if id is None:
            id = f"item_{uuid.uuid4().hex[:8]}"
        
        if dependencies is None:
            dependencies = []
        
        return WorkItem(
            id=id,
            title=title,
            description=description,
            dependencies=dependencies,
            status=status,
            kind=kind,
            assigned_uid=assigned_uid,
            **kwargs
        )
    
    @staticmethod
    def create_work_item_with_result(
        id: str = None,
        title: str = "Completed Item",
        success: bool = True,
        result_content: str = "Task completed successfully",
        **kwargs
    ) -> WorkItem:
        """
        Create a WorkItem with a result for testing.
        
        Args:
            id: Item ID
            title: Item title
            success: Whether the result indicates success
            result_content: Content of the result
            **kwargs: Additional WorkItem arguments
            
        Returns:
            WorkItem with result attached
        """
        result = WorkItemResult(
            success=success,
            content=result_content,
            data={"status": "completed" if success else "failed"}
        )
        
        return WorkPlanFactory.create_work_item(
            id=id,
            title=title,
            status=WorkItemStatus.DONE if success else WorkItemStatus.FAILED,
            result_ref=result,
            **kwargs
        )
    
    @staticmethod
    def create_simple_work_plan(
        item_count: int = 3,
        owner_uid: str = "test_orchestrator",
        thread_id: str = None,
        summary: str = "Test Work Plan",
        **kwargs
    ) -> WorkPlan:
        """
        Create a simple WorkPlan with sequential items.
        
        Args:
            item_count: Number of items to create
            owner_uid: UID of the orchestrator owning the plan
            thread_id: Thread ID (generates one if not provided)
            summary: Plan summary
            **kwargs: Additional WorkPlan arguments
            
        Returns:
            WorkPlan instance with items
        """
        if thread_id is None:
            thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        
        items = {}
        for i in range(1, item_count + 1):
            item_id = f"item_{i}"
            dependencies = [f"item_{i-1}"] if i > 1 else []
            
            items[item_id] = WorkPlanFactory.create_work_item(
                id=item_id,
                title=f"Work Item {i}",
                description=f"Description for item {i}",
                dependencies=dependencies
            )
        
        return WorkPlan(
            summary=summary,
            owner_uid=owner_uid,
            thread_id=thread_id,
            items=items,
            **kwargs
        )
    
    @staticmethod
    def create_complex_work_plan(
        owner_uid: str = "test_orchestrator",
        thread_id: str = None,
        **kwargs
    ) -> WorkPlan:
        """
        Create a complex WorkPlan with various statuses and dependencies.
        
        Args:
            owner_uid: UID of the orchestrator owning the plan
            thread_id: Thread ID
            **kwargs: Additional WorkPlan arguments
            
        Returns:
            WorkPlan with items in various states
        """
        if thread_id is None:
            thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        
        items = {
            "ready_item": WorkPlanFactory.create_work_item(
                id="ready_item",
                title="Ready Item",
                description="Item ready for execution",
                dependencies=[],
                status=WorkItemStatus.PENDING,
                kind=WorkItemKind.LOCAL
            ),
            "in_progress_item": WorkPlanFactory.create_work_item(
                id="in_progress_item",
                title="In Progress Item",
                description="Item currently being executed",
                dependencies=[],
                status=WorkItemStatus.IN_PROGRESS,
                kind=WorkItemKind.REMOTE,
                assigned_uid="worker_1"
            ),
            "waiting_item": WorkPlanFactory.create_work_item(
                id="waiting_item",
                title="Waiting Item",
                description="Item in progress (remote delegation)",
                dependencies=[],
                status=WorkItemStatus.IN_PROGRESS,
                kind=WorkItemKind.REMOTE,
                assigned_uid="worker_2",
                correlation_task_id="task_123"
            ),
            "done_item": WorkPlanFactory.create_work_item_with_result(
                id="done_item",
                title="Completed Item",
                success=True
            ),
            "failed_item": WorkPlanFactory.create_work_item(
                id="failed_item",
                title="Failed Item",
                description="Item that failed",
                status=WorkItemStatus.FAILED,
                error="Task failed due to error",
                retry_count=3
            ),
            "blocked_item": WorkPlanFactory.create_work_item(
                id="blocked_item",
                title="Blocked Item",
                description="Item blocked by dependencies",
                dependencies=["in_progress_item", "waiting_item"],
                status=WorkItemStatus.PENDING
            )
        }
        
        return WorkPlan(
            summary="Complex Test Work Plan",
            owner_uid=owner_uid,
            thread_id=thread_id,
            items=items,
            **kwargs
        )
    
    @staticmethod
    def create_parallel_work_plan(
        parallel_count: int = 3,
        owner_uid: str = "test_orchestrator",
        thread_id: str = None,
        **kwargs
    ) -> WorkPlan:
        """
        Create a WorkPlan with parallel independent items.
        
        Args:
            parallel_count: Number of parallel items
            owner_uid: UID of the orchestrator owning the plan
            thread_id: Thread ID
            **kwargs: Additional WorkPlan arguments
            
        Returns:
            WorkPlan with independent parallel items
        """
        if thread_id is None:
            thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        
        items = {}
        for i in range(1, parallel_count + 1):
            item_id = f"parallel_item_{i}"
            items[item_id] = WorkPlanFactory.create_work_item(
                id=item_id,
                title=f"Parallel Item {i}",
                description=f"Independent parallel task {i}",
                dependencies=[],  # No dependencies - can run in parallel
                kind=WorkItemKind.REMOTE,
                assigned_uid=f"worker_{i}"
            )
        
        return WorkPlan(
            summary="Parallel Execution Work Plan",
            owner_uid=owner_uid,
            thread_id=thread_id,
            items=items,
            **kwargs
        )
