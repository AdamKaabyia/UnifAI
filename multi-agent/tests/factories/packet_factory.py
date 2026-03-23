"""
Factory for creating IEM packets for testing.

Provides factory methods to create properly formatted IEM packets
with correct addressing and payload structure.
"""

from typing import Optional

from mas.core.iem.packets import TaskPacket
from mas.core.iem.models import ElementAddress
from mas.elements.nodes.common.workload import Task


class PacketFactory:
    """
    Factory for creating IEM packets for testing.
    
    Provides static methods to create TaskPacket objects with proper
    addressing and structure for testing IEM communication.
    """
    
    @staticmethod
    def create_task_packet(
        task: Task,
        src_uid: str,
        dst_uid: str
    ) -> TaskPacket:
        """
        Create a TaskPacket with proper IEM addressing.
        
        Args:
            task: The Task to wrap in packet
            src_uid: Source node UID
            dst_uid: Destination node UID
            
        Returns:
            TaskPacket with proper addressing
        """
        return TaskPacket.create(
            src=ElementAddress(uid=src_uid),
            dst=ElementAddress(uid=dst_uid),
            task=task
        )
    
    @staticmethod
    def create_request_packet(
        content: str,
        thread_id: str,
        src_uid: str = "user",
        dst_uid: str = "orchestrator",
        **task_kwargs
    ) -> TaskPacket:
        """
        Create a request packet (task without correlation).
        
        Args:
            content: Task content
            thread_id: Thread ID
            src_uid: Source node UID
            dst_uid: Destination node UID
            **task_kwargs: Additional Task arguments
            
        Returns:
            TaskPacket representing a request
        """
        task = Task(
            content=content,
            thread_id=thread_id,
            created_by=src_uid,
            should_respond=True,
            response_to=src_uid,
            **task_kwargs
        )
        
        return PacketFactory.create_task_packet(task, src_uid, dst_uid)
    
    @staticmethod
    def create_response_packet(
        response_content: str,
        correlation_task_id: str,
        thread_id: str,
        src_uid: str = "agent",
        dst_uid: str = "orchestrator",
        success: bool = True,
        **task_kwargs
    ) -> TaskPacket:
        """
        Create a response packet (task with correlation).
        
        Args:
            response_content: Response content
            correlation_task_id: ID of task being responded to
            thread_id: Thread ID
            src_uid: Source node UID (responding agent)
            dst_uid: Destination node UID (requester)
            success: Whether response indicates success
            **task_kwargs: Additional Task arguments
            
        Returns:
            TaskPacket representing a response
        """
        task = Task(
            content=response_content,
            thread_id=thread_id,
            created_by=src_uid,
            correlation_task_id=correlation_task_id,
            result={"success": success, "content": response_content},
            **task_kwargs
        )
        
        return PacketFactory.create_task_packet(task, src_uid, dst_uid)
    
    @staticmethod
    def create_delegation_packet(
        content: str,
        thread_id: str,
        src_uid: str = "orchestrator",
        dst_uid: str = "worker",
        **task_kwargs
    ) -> TaskPacket:
        """
        Create a delegation packet (orchestrator to worker).
        
        Args:
            content: Task content to delegate
            thread_id: Thread ID
            src_uid: Source node UID (orchestrator)
            dst_uid: Destination node UID (worker)
            **task_kwargs: Additional Task arguments
            
        Returns:
            TaskPacket representing a delegation
        """
        from tests.factories.task_factory import TaskFactory
        
        task = TaskFactory.create_delegation_task(
            content=content,
            thread_id=thread_id,
            delegated_to=dst_uid,
            created_by=src_uid,
            **task_kwargs
        )
        
        return PacketFactory.create_task_packet(task, src_uid, dst_uid)
    
    @staticmethod
    def create_batch_packets(
        count: int,
        src_uid: str,
        dst_uid: str,
        thread_id: str,
        content_prefix: str = "Task"
    ) -> list[TaskPacket]:
        """
        Create a batch of task packets.
        
        Args:
            count: Number of packets to create
            src_uid: Source node UID
            dst_uid: Destination node UID
            thread_id: Thread ID (same for all)
            content_prefix: Prefix for task content
            
        Returns:
            List of TaskPacket instances
        """
        from tests.factories.task_factory import TaskFactory
        
        tasks = TaskFactory.create_batch_tasks(
            count=count,
            content_prefix=content_prefix,
            thread_id=thread_id,
            created_by=src_uid
        )
        
        return [
            PacketFactory.create_task_packet(task, src_uid, dst_uid)
            for task in tasks
        ]
