"""
Comprehensive tests for IEM-workload task coordination.

Tests task distribution, coordination, and completion tracking through IEM.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any
from unittest.mock import Mock, patch

from mas.core.iem.messenger import DefaultInterMessenger
from mas.core.iem.models import ElementAddress
from mas.core.iem.packets import TaskPacket
from mas.elements.nodes.common.workload import Task, ThreadStatus
from mas.elements.nodes.common.workload.models import AgentResult as BaseAgentResult
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any

# Define TaskStatus for testing since it's not in the actual workload module
class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Define test-specific AgentResult that includes status and task coordination fields
@dataclass
class AgentResult:
    task_id: str
    agent_id: str
    status: TaskStatus
    output: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

from mas.graph.state.graph_state import Channel
from tests.fixtures.iem_testing_tools import (
    create_test_state_view, create_test_step_context, 
    PacketFactory, IEMPerformanceMonitor
)


class WorkloadCoordinator:
    """Simulates a workload coordinator node that distributes tasks via IEM."""
    
    def __init__(self, uid: str, state_view, context):
        self.uid = uid
        self.messenger = DefaultInterMessenger(
            state=state_view,
            identity=ElementAddress(uid=uid),
            context=context
        )
        self.pending_tasks = {}
        self.completed_tasks = {}
        self.worker_status = {}
    
    def distribute_task(self, task: Task, worker_uid: str) -> str:
        """Distribute a task to a worker via IEM."""
        packet = TaskPacket.create(
            src=ElementAddress(uid=self.uid),
            dst=ElementAddress(uid=worker_uid),
            task=task
        )
        
        packet_id = self.messenger.send_packet(packet)
        self.pending_tasks[task.task_id] = {
            "task": task,
            "worker": worker_uid,
            "packet_id": packet_id,
            "sent_at": datetime.utcnow()
        }
        return packet_id
    
    def check_task_responses(self) -> List[AgentResult]:
        """Check for task completion responses."""
        inbox = self.messenger.inbox_packets()
        results = []
        
        for packet in inbox:
            if packet.type.value == "task":
                task = packet.extract_task()
                if task.result:
                    # Task completed
                    result = AgentResult(**task.result)
                    results.append(result)
                    
                    # Move from pending to completed
                    if task.task_id in self.pending_tasks:
                        self.completed_tasks[task.task_id] = {
                            **self.pending_tasks.pop(task.task_id),
                            "result": result,
                            "completed_at": datetime.utcnow()
                        }
                    
                    # Acknowledge the response
                    self.messenger.acknowledge(packet.id)
        
        return results
    
    def get_pending_task_count(self) -> int:
        """Get number of pending tasks."""
        return len(self.pending_tasks)
    
    def get_completed_task_count(self) -> int:
        """Get number of completed tasks."""
        return len(self.completed_tasks)


class WorkloadWorker:
    """Simulates a worker node that processes tasks via IEM."""
    
    def __init__(self, uid: str, state_view, context):
        self.uid = uid
        self.messenger = DefaultInterMessenger(
            state=state_view,
            identity=ElementAddress(uid=uid),
            context=context
        )
        self.processing_tasks = {}
        self.completed_tasks = {}
        self.processing_delay = 0.1  # Simulated processing time
    
    def check_for_tasks(self) -> List[Task]:
        """Check for incoming tasks."""
        inbox = self.messenger.inbox_packets()
        new_tasks = []
        
        for packet in inbox:
            if packet.type.value == "task":
                task = packet.extract_task()
                new_tasks.append(task)
                
                # Start processing
                self.processing_tasks[task.task_id] = {
                    "task": task,
                    "packet_id": packet.id,
                    "started_at": datetime.utcnow()
                }
                
                # Acknowledge receipt
                self.messenger.acknowledge(packet.id)
        
        return new_tasks
    
    def process_tasks(self, simulate_work: bool = True) -> List[AgentResult]:
        """Process pending tasks."""
        import time
        results = []
        
        for task_id, task_info in list(self.processing_tasks.items()):
            task = task_info["task"]
            
            if simulate_work:
                time.sleep(self.processing_delay)
            
            # Create result
            result = AgentResult(
                task_id=task.task_id,
                agent_id=self.uid,
                status=TaskStatus.COMPLETED,
                output=f"Processed: {task.content}",
                metadata={"processed_by": self.uid, "worker_id": self.uid}
            )
            
            # Update task with result
            task.result = result.__dict__
            # Note: The actual Task model doesn't have status field, but we can add it dynamically for testing
            task.__dict__['status'] = TaskStatus.COMPLETED
            task.processed_by = self.uid
            task.processed_at = datetime.utcnow()
                
            # Send result back to coordinator
            response_packet = TaskPacket.create(
                src=ElementAddress(uid=self.uid),
                dst=ElementAddress(uid=task.created_by),
                task=task
            )
            
            self.messenger.send_packet(response_packet)
            
            # Move to completed
            self.completed_tasks[task_id] = {
                **self.processing_tasks.pop(task_id),
                "result": result,
                "completed_at": datetime.utcnow()
            }
            
            results.append(result)
        
        return results
    
    def get_processing_count(self) -> int:
        """Get number of tasks currently processing."""
        return len(self.processing_tasks)


class TestTaskCoordination:
    """Test suite for IEM-workload task coordination."""
    
    def test_simple_task_distribution(self):
        """Test basic task distribution from coordinator to worker."""
        state = create_test_state_view()
        
        # Create coordinator and worker contexts
        coord_context = create_test_step_context("coordinator", ["worker1"])
        worker_context = create_test_step_context("worker1", ["coordinator"])
        
        coordinator = WorkloadCoordinator("coordinator", state, coord_context)
        worker = WorkloadWorker("worker1", state, worker_context)
        
        # Create and distribute task
        task = Task.create(
            content="Process this data",
            created_by="coordinator",
            data={"input": "test_data"}
        )
        # Add assigned_to field for testing
        task.__dict__['assigned_to'] = "worker1"
        
        packet_id = coordinator.distribute_task(task, "worker1")
        assert packet_id is not None
        assert coordinator.get_pending_task_count() == 1
        
        # Worker checks for tasks
        received_tasks = worker.check_for_tasks()
        assert len(received_tasks) == 1
        assert received_tasks[0].content == "Process this data"
        assert worker.get_processing_count() == 1
        
        # Worker processes task
        results = worker.process_tasks(simulate_work=False)
        assert len(results) == 1
        assert results[0].status == TaskStatus.COMPLETED
        assert worker.get_processing_count() == 0
        
        # Coordinator checks for responses
        coordinator_results = coordinator.check_task_responses()
        assert len(coordinator_results) == 1
        assert coordinator.get_pending_task_count() == 0
        assert coordinator.get_completed_task_count() == 1
    
    def test_multiple_task_distribution(self):
        """Test distributing multiple tasks to multiple workers."""
        state = create_test_state_view()
        
        coord_context = create_test_step_context("coordinator", ["worker1", "worker2", "worker3"])
        worker1_context = create_test_step_context("worker1", ["coordinator"])
        worker2_context = create_test_step_context("worker2", ["coordinator"])
        worker3_context = create_test_step_context("worker3", ["coordinator"])
        
        coordinator = WorkloadCoordinator("coordinator", state, coord_context)
        workers = [
            WorkloadWorker("worker1", state, worker1_context),
            WorkloadWorker("worker2", state, worker2_context),
            WorkloadWorker("worker3", state, worker3_context)
        ]
        
        # Distribute tasks round-robin
        tasks = []
        for i in range(9):  # 3 tasks per worker
            task = Task.create(
                content=f"Task {i}",
                created_by="coordinator",
                data={"task_index": i}
            )
            tasks.append(task)
            
            worker_id = f"worker{(i % 3) + 1}"
            coordinator.distribute_task(task, worker_id)
        
        assert coordinator.get_pending_task_count() == 9
        
        # Workers process tasks
        all_results = []
        for worker in workers:
            received_tasks = worker.check_for_tasks()
            assert len(received_tasks) == 3  # Each worker gets 3 tasks
            
            results = worker.process_tasks(simulate_work=False)
            assert len(results) == 3
            all_results.extend(results)
        
        assert len(all_results) == 9
        
        # Coordinator collects all results
        coordinator_results = coordinator.check_task_responses()
        assert len(coordinator_results) == 9
        assert coordinator.get_pending_task_count() == 0
        assert coordinator.get_completed_task_count() == 9
    
    def test_task_coordination_with_failures(self):
        """Test task coordination with worker failures."""
        state = create_test_state_view()
        
        coord_context = create_test_step_context("coordinator", ["worker1", "worker2"])
        worker1_context = create_test_step_context("worker1", ["coordinator"])
        worker2_context = create_test_step_context("worker2", ["coordinator"])
        
        coordinator = WorkloadCoordinator("coordinator", state, coord_context)
        worker1 = WorkloadWorker("worker1", state, worker1_context)
        worker2 = WorkloadWorker("worker2", state, worker2_context)
        
        # Distribute tasks
        tasks = []
        for i in range(4):
            task = Task.create(
                content=f"Task {i}",
                created_by="coordinator"
            )
            tasks.append(task)
            
            worker_id = "worker1" if i < 2 else "worker2"
            coordinator.distribute_task(task, worker_id)
        
        # Worker1 processes normally
        worker1_tasks = worker1.check_for_tasks()
        worker1_results = worker1.process_tasks(simulate_work=False)
        assert len(worker1_results) == 2
        
        # Worker2 simulates failure (doesn't process tasks)
        worker2_tasks = worker2.check_for_tasks()
        assert len(worker2_tasks) == 2
        # Don't call worker2.process_tasks() to simulate failure
        
        # Coordinator should see partial results
        coordinator_results = coordinator.check_task_responses()
        assert len(coordinator_results) == 2  # Only from worker1
        assert coordinator.get_pending_task_count() == 2  # worker2 tasks still pending
        assert coordinator.get_completed_task_count() == 2
    
    def test_task_coordination_with_timeouts(self):
        """Test task coordination with timeout handling."""
        state = create_test_state_view()
        
        coord_context = create_test_step_context("coordinator", ["worker1"])
        worker_context = create_test_step_context("worker1", ["coordinator"])
        
        coordinator = WorkloadCoordinator("coordinator", state, coord_context)
        worker = WorkloadWorker("worker1", state, worker_context)
        
        # Create task with short TTL
        task = Task.create(
            content="Time-sensitive task",
            created_by="coordinator"
        )
        
        # Create packet with short TTL
        packet = TaskPacket.create(
            src=ElementAddress(uid="coordinator"),
            dst=ElementAddress(uid="worker1"),
            task=task
        )
        packet.ttl = timedelta(milliseconds=1)  # Very short TTL
        
        # Send packet directly (bypassing coordinator.distribute_task for TTL control)
        coordinator.messenger.send_packet(packet)
        
        # Wait for TTL to expire
        import time
        time.sleep(0.01)  # 10ms wait
        
        # Worker should not receive expired packet
        received_tasks = worker.check_for_tasks()
        assert len(received_tasks) == 0  # Expired packet filtered out
    
    def test_task_coordination_with_priorities(self):
        """Test task coordination with priority handling."""
        state = create_test_state_view()
        
        coord_context = create_test_step_context("coordinator", ["worker1"])
        worker_context = create_test_step_context("worker1", ["coordinator"])
        
        coordinator = WorkloadCoordinator("coordinator", state, coord_context)
        worker = WorkloadWorker("worker1", state, worker_context)
        
        # Create tasks with different priorities
        high_priority_task = Task.create(
            content="High priority task",
            created_by="coordinator",
            data={"priority": "high"}
        )
        
        low_priority_task = Task.create(
            content="Low priority task",
            created_by="coordinator",
            data={"priority": "low"}
        )
        
        # Distribute tasks
        coordinator.distribute_task(low_priority_task, "worker1")
        coordinator.distribute_task(high_priority_task, "worker1")
        
        # Worker receives tasks
        received_tasks = worker.check_for_tasks()
        assert len(received_tasks) == 2
        
        # Verify task data includes priority information
        priorities = [task.data.get("priority") for task in received_tasks]
        assert "high" in priorities
        assert "low" in priorities
        
        # Process tasks
        results = worker.process_tasks(simulate_work=False)
        assert len(results) == 2
    
    def test_task_coordination_performance_monitoring(self):
        """Test task coordination with performance monitoring."""
        state = create_test_state_view()
        monitor = IEMPerformanceMonitor()
        
        coord_context = create_test_step_context("coordinator", ["worker1", "worker2"])
        worker1_context = create_test_step_context("worker1", ["coordinator"])
        worker2_context = create_test_step_context("worker2", ["coordinator"])
        
        coordinator = WorkloadCoordinator("coordinator", state, coord_context)
        worker1 = WorkloadWorker("worker1", state, worker1_context)
        worker2 = WorkloadWorker("worker2", state, worker2_context)
        
        # Monitor task distribution
        with monitor.monitor_operation("task_distribution") as op_id:
            tasks = []
            for i in range(10):
                task = Task.create(
                    content=f"Performance test task {i}",
                    created_by="coordinator"
                )
                tasks.append(task)
                
                worker_id = "worker1" if i % 2 == 0 else "worker2"
                coordinator.distribute_task(task, worker_id)
        
        # Monitor task processing
        with monitor.monitor_operation("task_processing") as op_id:
            # Workers process tasks
            for worker in [worker1, worker2]:
                received_tasks = worker.check_for_tasks()
                worker.process_tasks(simulate_work=False)
        
        # Monitor result collection
        with monitor.monitor_operation("result_collection") as op_id:
            coordinator_results = coordinator.check_task_responses()
        
        # Verify performance metrics
        distribution_stats = monitor.get_operation_stats("task_distribution")
        processing_stats = monitor.get_operation_stats("task_processing")
        collection_stats = monitor.get_operation_stats("result_collection")
        
        assert distribution_stats["success_count"] == 1
        assert processing_stats["success_count"] == 1
        assert collection_stats["success_count"] == 1
        
        assert len(coordinator_results) == 10
        assert coordinator.get_completed_task_count() == 10
    
    def test_task_coordination_complex_workflow(self):
        """Test complex multi-stage task coordination workflow."""
        state = create_test_state_view()
        
        # Create a pipeline: preprocessor -> processor -> postprocessor
        prep_context = create_test_step_context("preprocessor", ["processor"])
        proc_context = create_test_step_context("processor", ["preprocessor", "postprocessor"])
        post_context = create_test_step_context("postprocessor", ["processor"])
        
        preprocessor = WorkloadWorker("preprocessor", state, prep_context)
        processor = WorkloadWorker("processor", state, proc_context)
        postprocessor = WorkloadWorker("postprocessor", state, post_context)
        
        # Stage 1: Initial task to preprocessor
        initial_task = Task.create(
            content="Raw data to preprocess",
            created_by="external_system",
            data={"stage": "initial", "data": "raw_input"}
        )
        
        # Manually add initial task
        packet = TaskPacket.create(
            src=ElementAddress(uid="external_system"),
            dst=ElementAddress(uid="preprocessor"),
            task=initial_task
        )
        state[Channel.INTER_PACKETS] = [packet]
        
        # Stage 1: Preprocessor processes and forwards
        prep_tasks = preprocessor.check_for_tasks()
        assert len(prep_tasks) == 1
        
        # Modify the preprocessing logic
        for task_id, task_info in list(preprocessor.processing_tasks.items()):
            task = task_info["task"]
            
            # Create processed task for next stage
            processed_task = Task.create(
                content="Preprocessed data",
                created_by="preprocessor",
                data={"stage": "preprocessed", "data": "processed_input"},
                parent_task_id=task.task_id
            )
            
            # Send to processor
            packet = TaskPacket.create(
                src=ElementAddress(uid="preprocessor"),
                dst=ElementAddress(uid="processor"),
                task=processed_task
            )
            preprocessor.messenger.send_packet(packet)
            
            # Complete preprocessing
            result = AgentResult(
                task_id=task.task_id,
                agent_id="preprocessor",
                status=TaskStatus.COMPLETED,
                output="Preprocessing completed"
            )
            preprocessor.completed_tasks[task_id] = {
                **preprocessor.processing_tasks.pop(task_id),
                "result": result,
                "completed_at": datetime.utcnow()
            }
        
        # Stage 2: Processor processes and forwards
        proc_tasks = processor.check_for_tasks()
        assert len(proc_tasks) == 1
        assert proc_tasks[0].data["stage"] == "preprocessed"
        
        # Similar processing for processor -> postprocessor
        for task_id, task_info in list(processor.processing_tasks.items()):
            task = task_info["task"]
            
            final_task = Task.create(
                content="Final processed data",
                created_by="processor",
                data={"stage": "final", "data": "final_output"},
                parent_task_id=task.task_id
            )
            
            packet = TaskPacket.create(
                src=ElementAddress(uid="processor"),
                dst=ElementAddress(uid="postprocessor"),
                task=final_task
            )
            processor.messenger.send_packet(packet)
            
            result = AgentResult(
                task_id=task.task_id,
                agent_id="processor",
                status=TaskStatus.COMPLETED,
                output="Processing completed"
            )
            processor.completed_tasks[task_id] = {
                **processor.processing_tasks.pop(task_id),
                "result": result,
                "completed_at": datetime.utcnow()
            }
        
        # Stage 3: Postprocessor completes workflow
        post_tasks = postprocessor.check_for_tasks()
        assert len(post_tasks) == 1
        assert post_tasks[0].data["stage"] == "final"
        
        post_results = postprocessor.process_tasks(simulate_work=False)
        assert len(post_results) == 1
        assert post_results[0].output == "Processed: Final processed data"
        
        # Verify complete workflow
        assert len(preprocessor.completed_tasks) == 1
        assert len(processor.completed_tasks) == 1
        assert len(postprocessor.completed_tasks) == 1
    
    def test_task_coordination_error_recovery(self):
        """Test task coordination with error recovery mechanisms."""
        state = create_test_state_view()
        
        coord_context = create_test_step_context("coordinator", ["worker1", "worker2"])
        worker1_context = create_test_step_context("worker1", ["coordinator"])
        worker2_context = create_test_step_context("worker2", ["coordinator"])
        
        coordinator = WorkloadCoordinator("coordinator", state, coord_context)
        worker1 = WorkloadWorker("worker1", state, worker1_context)
        worker2 = WorkloadWorker("worker2", state, worker2_context)
        
        # Create task that will "fail"
        failing_task = Task.create(
            content="This task will fail",
            created_by="coordinator",
            data={"simulate_failure": True}
        )
        
        normal_task = Task.create(
            content="This task will succeed",
            created_by="coordinator"
        )
        
        # Distribute tasks
        coordinator.distribute_task(failing_task, "worker1")
        coordinator.distribute_task(normal_task, "worker2")
        
        # Worker1 simulates failure
        worker1_tasks = worker1.check_for_tasks()
        assert len(worker1_tasks) == 1
        
        # Simulate task failure
        for task_id, task_info in list(worker1.processing_tasks.items()):
            task = task_info["task"]
            
            if task.data.get("simulate_failure"):
                # Create error result
                error_result = AgentResult(
                    task_id=task.task_id,
                    agent_id="worker1",
                    status=TaskStatus.FAILED,
                    output="Task failed due to error",
                    error="Simulated processing error"
                )
                
                # Send error response
                task.result = error_result.__dict__
                task.__dict__['status'] = TaskStatus.FAILED
                task.error = "Simulated processing error"  # Error is now a string
                
                response_packet = TaskPacket.create(
                    src=ElementAddress(uid="worker1"),
                    dst=ElementAddress(uid=task.created_by),
                    task=task
                )
                
                worker1.messenger.send_packet(response_packet)
                
                worker1.completed_tasks[task_id] = {
                    **worker1.processing_tasks.pop(task_id),
                    "result": error_result,
                    "completed_at": datetime.utcnow()
                }
        
        # Worker2 processes normally
        worker2_tasks = worker2.check_for_tasks()
        worker2_results = worker2.process_tasks(simulate_work=False)
        
        # Coordinator handles mixed results
        coordinator_results = coordinator.check_task_responses()
        assert len(coordinator_results) == 2
        
        # Verify error handling
        failed_results = [r for r in coordinator_results if r.status == TaskStatus.FAILED]
        successful_results = [r for r in coordinator_results if r.status == TaskStatus.COMPLETED]
        
        assert len(failed_results) == 1
        assert len(successful_results) == 1
        assert coordinator.get_completed_task_count() == 2  # Both completed (success + failure)
