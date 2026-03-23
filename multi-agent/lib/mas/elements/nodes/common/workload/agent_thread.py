"""
Utilities for managing agentic task threads.

Thread ID represents task execution context for agent coordination.
Provides hierarchical threading for subtasks and parallel execution.
"""

import uuid
from typing import Optional


class AgentThread:
    """Utility for managing agentic task threads."""
    
    @staticmethod
    def create(initiator: str, task_description: str) -> str:
        """
        Create main task thread.
        
        Format: {initiator}:{task_type}:{unique_id}
        Example: "orchestrator:research_project:abc12345"
        
        Args:
            initiator: Node UID that creates the thread
            task_description: Brief description of the task
            
        Returns:
            Thread ID string
        """
        task_key = task_description.lower().replace(' ', '_')[:20]
        return f"{initiator}:{task_key}:{uuid.uuid4().hex[:8]}"
    
    @staticmethod
    def spawn_subtask(parent_thread: str, subtask_description: str) -> str:
        """
        Spawn subtask thread.
        
        Format: {parent_thread}.{subtask_name}
        Example: "orchestrator:research_project:abc12345.data_analysis"
        
        Args:
            parent_thread: Parent thread ID
            subtask_description: Brief description of the subtask
            
        Returns:
            Subtask thread ID string
        """
        subtask_key = subtask_description.lower().replace(' ', '_')[:15]
        return f"{parent_thread}.{subtask_key}"
    
    @staticmethod
    def spawn_parallel(parent_thread: str, index: int) -> str:
        """
        Spawn parallel thread.
        
        Format: {parent_thread}.p{index}
        Example: "orchestrator:research_project:abc12345.p1"
        
        Args:
            parent_thread: Parent thread ID
            index: Parallel task index
            
        Returns:
            Parallel thread ID string
        """
        return f"{parent_thread}.p{index}"
    
    @staticmethod
    def get_parent_thread(thread_id: str) -> Optional[str]:
        """
        Extract parent thread from hierarchical thread ID.
        
        Args:
            thread_id: Thread ID to parse
            
        Returns:
            Parent thread ID or None if root thread
        """
        if '.' in thread_id:
            return thread_id.rsplit('.', 1)[0]
        return None
    
    @staticmethod
    def get_root_thread(thread_id: str) -> str:
        """
        Get the root thread (removes all subtask components).
        
        Args:
            thread_id: Thread ID to parse
            
        Returns:
            Root thread ID
        """
        return thread_id.split('.')[0]
    
    @staticmethod
    def is_subtask_thread(thread_id: str) -> bool:
        """
        Check if this is a subtask thread.
        
        Args:
            thread_id: Thread ID to check
            
        Returns:
            True if subtask thread, False if root thread
        """
        return '.' in thread_id
