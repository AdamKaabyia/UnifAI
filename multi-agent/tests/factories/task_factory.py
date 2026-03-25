"""
Factory for creating tasks with various configurations.

Provides factory methods to create Task objects with common patterns,
reducing duplication in test setup.
"""

import uuid
from typing import Optional, Dict, Any

from mas.elements.nodes.common.workload import Task


class TaskFactory:
    """
    Factory for creating Task objects with various configurations.
    
    Provides static methods to create tasks for different scenarios
    like simple tasks, response tasks, delegation tasks, etc.
    """
    
    @staticmethod
    def create_simple_task(
        content: str,
        thread_id: str = None,
        created_by: str = "test_user",
        **kwargs
    ) -> Task:
        """
        Create a simple task for testing.
        
        Args:
            content: Task content
            thread_id: Thread ID (generates one if not provided)
            created_by: Creator UID
            **kwargs: Additional Task arguments
            
        Returns:
            Task instance
        """
        if thread_id is None:
            thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        
        return Task(
            content=content,
            thread_id=thread_id,
            created_by=created_by,
            should_respond=False,
            **kwargs
        )
    
    @staticmethod
    def create_task_with_response(
        content: str,
        thread_id: str = None,
        created_by: str = "test_user",
        response_to: str = "test_requester",
        **kwargs
    ) -> Task:
        """
        Create a task that requires a response.
        
        Args:
            content: Task content
            thread_id: Thread ID
            created_by: Creator UID
            response_to: UID to respond to
            **kwargs: Additional Task arguments
            
        Returns:
            Task instance configured to require response
        """
        if thread_id is None:
            thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        
        return Task(
            content=content,
            thread_id=thread_id,
            created_by=created_by,
            should_respond=True,
            response_to=response_to,
            **kwargs
        )
    
    @staticmethod
    def create_response_task(
        response_content: str,
        correlation_task_id: str,
        thread_id: str,
        created_by: str = "test_agent",
        success: bool = True,
        result_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Task:
        """
        Create a response task to an existing task.
        
        Args:
            response_content: Content of the response
            correlation_task_id: ID of the task being responded to
            thread_id: Thread ID
            created_by: Creator UID (responding agent)
            success: Whether the response indicates success
            result_data: Additional result data
            **kwargs: Additional Task arguments
            
        Returns:
            Task instance configured as a response
        """
        if result_data is None:
            result_data = {"success": success, "content": response_content}
        else:
            result_data = {"success": success, **result_data}
        
        return Task(
            content=response_content,
            thread_id=thread_id,
            created_by=created_by,
            correlation_task_id=correlation_task_id,
            result=result_data,
            **kwargs
        )
    
    @staticmethod
    def create_delegation_task(
        content: str,
        thread_id: str,
        delegated_to: str,
        created_by: str = "test_orchestrator",
        **kwargs
    ) -> Task:
        """
        Create a task for delegation to another node.
        
        Args:
            content: Task content
            thread_id: Thread ID
            delegated_to: UID of node to delegate to
            created_by: Creator UID (delegating node)
            **kwargs: Additional Task arguments
            
        Returns:
            Task instance configured for delegation
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        
        return Task(
            task_id=task_id,
            content=content,
            thread_id=thread_id,
            created_by=created_by,
            should_respond=True,
            response_to=created_by,
            **kwargs
        )
    
    @staticmethod
    def create_batch_tasks(
        count: int,
        content_prefix: str = "Task",
        thread_id: str = None,
        **kwargs
    ) -> list[Task]:
        """
        Create a batch of tasks for testing.
        
        Args:
            count: Number of tasks to create
            content_prefix: Prefix for task content
            thread_id: Thread ID (same for all tasks)
            **kwargs: Additional Task arguments
            
        Returns:
            List of Task instances
        """
        if thread_id is None:
            thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        
        tasks = []
        for i in range(1, count + 1):
            task = TaskFactory.create_simple_task(
                content=f"{content_prefix} {i}",
                thread_id=thread_id,
                **kwargs
            )
            tasks.append(task)
        
        return tasks
    
    @staticmethod
    def create_orchestration_task(
        content: str,
        thread_id: str = None,
        created_by: str = "user",
        **kwargs
    ) -> Task:
        """
        Create a task suitable for orchestrator processing.
        
        Args:
            content: Task content (typically a high-level goal)
            thread_id: Thread ID
            created_by: Creator UID
            **kwargs: Additional Task arguments
            
        Returns:
            Task instance configured for orchestration
        """
        if thread_id is None:
            thread_id = f"orchestration_thread_{uuid.uuid4().hex[:8]}"
        
        return Task(
            content=content,
            thread_id=thread_id,
            created_by=created_by,
            should_respond=True,
            response_to=created_by,
            **kwargs
        )
