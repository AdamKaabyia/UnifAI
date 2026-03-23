"""
Comprehensive tests for IEM-workload thread management integration.

Tests thread coordination, workspace sharing, and multi-threaded task execution.
"""

import pytest
import uuid
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from mas.core.iem.messenger import DefaultInterMessenger
from mas.core.iem.models import ElementAddress
from mas.core.iem.packets import TaskPacket, SystemPacket
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


class ThreadManager:
    """Manages threads and coordinates work through IEM."""
    
    def __init__(self, uid: str, state_view, context):
        self.uid = uid
        self.messenger = DefaultInterMessenger(
            state=state_view,
            identity=ElementAddress(uid=uid),
            context=context
        )
        self.active_threads = {}
        self.thread_workspaces = {}
        self.thread_results = {}
        self.lock = threading.Lock()
    
    def create_thread(self, thread_id: str, thread_type: str = "execution") -> bool:
        """Create a new thread."""
        with self.lock:
            if thread_id in self.active_threads:
                return False
            
            self.active_threads[thread_id] = {
                "id": thread_id,
                "type": thread_type,
                "created_at": datetime.utcnow(),
                "status": "active",
                "tasks": [],
                "workspace": f"workspace_{thread_id}"
            }
            
            self.thread_workspaces[thread_id] = {
                "data": {},
                "shared_state": {},
                "created_at": datetime.utcnow()
            }
            
            # Broadcast thread creation
            self._broadcast_thread_event("thread_created", thread_id)
            return True
    
    def assign_task_to_thread(self, task: Task, thread_id: str) -> bool:
        """Assign a task to a specific thread."""
        with self.lock:
            if thread_id not in self.active_threads:
                return False
            
            # Update task with thread information
            task.thread_id = thread_id
            task.correlation_task_id = thread_id
            
            self.active_threads[thread_id]["tasks"].append(task.task_id)
            
            # Send task via IEM with thread context
            packet = TaskPacket.create(
                src=ElementAddress(uid=self.uid),
                dst=ElementAddress(uid=getattr(task, 'assigned_to', "worker")),
                task=task
            )
            
            self.messenger.send_packet(packet)
            return True
    
    def update_thread_workspace(self, thread_id: str, data: Dict) -> bool:
        """Update thread workspace data."""
        with self.lock:
            if thread_id not in self.thread_workspaces:
                return False
            
            self.thread_workspaces[thread_id]["data"].update(data)
            self.thread_workspaces[thread_id]["updated_at"] = datetime.utcnow()
            
            # Broadcast workspace update
            self._broadcast_thread_event("workspace_updated", thread_id, data)
            return True
    
    def close_thread(self, thread_id: str) -> bool:
        """Close a thread and clean up resources."""
        with self.lock:
            if thread_id not in self.active_threads:
                return False
            
            self.active_threads[thread_id]["status"] = "closed"
            self.active_threads[thread_id]["closed_at"] = datetime.utcnow()
            
            # Broadcast thread closure
            self._broadcast_thread_event("thread_closed", thread_id)
            return True
    
    def _broadcast_thread_event(self, event_type: str, thread_id: str, data: Dict = None):
        """Broadcast thread events to adjacent nodes."""
        for node_uid in self.messenger.get_adjacent_nodes():
            event_packet = SystemPacket(
                src=ElementAddress(uid=self.uid),
                dst=ElementAddress(uid=node_uid),
                system_event=event_type,
                data={
                    "thread_id": thread_id,
                    "manager": self.uid,
                    "timestamp": datetime.utcnow().isoformat(),
                    **(data or {})
                }
            )
            self.messenger.send_packet(event_packet)
    
    def get_thread_status(self, thread_id: str) -> Optional[Dict]:
        """Get status of a specific thread."""
        with self.lock:
            return self.active_threads.get(thread_id)
    
    def get_all_threads(self) -> Dict:
        """Get status of all threads."""
        with self.lock:
            return self.active_threads.copy()


class ThreadAwareWorker:
    """Worker that participates in thread-based coordination."""
    
    def __init__(self, uid: str, state_view, context):
        self.uid = uid
        self.messenger = DefaultInterMessenger(
            state=state_view,
            identity=ElementAddress(uid=uid),
            context=context
        )
        self.thread_subscriptions = set()
        self.thread_workspaces = {}
        self.processing_tasks = {}
        self.lock = threading.Lock()
    
    def subscribe_to_thread(self, thread_id: str):
        """Subscribe to thread events."""
        with self.lock:
            self.thread_subscriptions.add(thread_id)
    
    def process_messages(self) -> Dict[str, List]:
        """Process incoming messages (tasks and thread events)."""
        inbox = self.messenger.inbox_packets()
        tasks = []
        events = []
        
        for packet in inbox:
            if packet.type.value == "task":
                task = packet.extract_task()
                tasks.append(task)
                
                # Start processing in thread context
                with self.lock:
                    self.processing_tasks[task.task_id] = {
                        "task": task,
                        "thread_id": task.thread_id,
                        "started_at": datetime.utcnow()
                    }
                
            elif packet.type.value == "system":
                events.append(packet)
                self._handle_thread_event(packet)
            
            self.messenger.acknowledge(packet.id)
        
        return {"tasks": tasks, "events": events}
    
    def _handle_thread_event(self, event_packet: SystemPacket):
        """Handle thread management events."""
        event_type = event_packet.system_event
        data = event_packet.data
        thread_id = data.get("thread_id")
        
        if not thread_id or thread_id not in self.thread_subscriptions:
            return
        
        with self.lock:
            if event_type == "thread_created":
                self.thread_workspaces[thread_id] = {
                    "created_at": datetime.utcnow(),
                    "data": {},
                    "manager": data.get("manager")
                }
            
            elif event_type == "workspace_updated":
                if thread_id in self.thread_workspaces:
                    self.thread_workspaces[thread_id]["data"].update(data)
                    self.thread_workspaces[thread_id]["updated_at"] = datetime.utcnow()
            
            elif event_type == "thread_closed":
                if thread_id in self.thread_workspaces:
                    self.thread_workspaces[thread_id]["status"] = "closed"
    
    def execute_tasks(self, simulate_work: bool = True) -> List[AgentResult]:
        """Execute tasks with thread awareness."""
        results = []
        
        with self.lock:
            tasks_to_process = list(self.processing_tasks.items())
        
        for task_id, task_info in tasks_to_process:
            task = task_info["task"]
            thread_id = task_info["thread_id"]
            
            if simulate_work:
                time.sleep(0.01)  # Simulate processing
            
            # Access thread workspace if available
            workspace_data = {}
            if thread_id and thread_id in self.thread_workspaces:
                workspace_data = self.thread_workspaces[thread_id]["data"].copy()
            
            # Create result with thread context
            result = AgentResult(
                task_id=task.task_id,
                agent_id=self.uid,
                status=TaskStatus.COMPLETED,
                output=f"Processed in thread {thread_id}: {task.content}",
                metadata={
                    "thread_id": thread_id,
                    "workspace_data": workspace_data,
                    "worker": self.uid
                }
            )
            
            # Send result back
            task.result = result.__dict__
            task.__dict__['status'] = TaskStatus.COMPLETED
            task.processed_by = self.uid
            task.processed_at = datetime.utcnow()
            
            response_packet = TaskPacket.create(
                src=ElementAddress(uid=self.uid),
                dst=ElementAddress(uid=task.created_by),
                task=task
            )
            
            self.messenger.send_packet(response_packet)
            results.append(result)
            
            # Remove from processing
            with self.lock:
                self.processing_tasks.pop(task_id, None)
        
        return results


class TestThreadManagement:
    """Test suite for IEM-workload thread management."""
    
    def test_basic_thread_creation_and_coordination(self):
        """Test basic thread creation and task coordination."""
        state = create_test_state_view()
        
        manager_context = create_test_step_context("thread_manager", ["worker1"])
        worker_context = create_test_step_context("worker1", ["thread_manager"])
        
        manager = ThreadManager("thread_manager", state, manager_context)
        worker = ThreadAwareWorker("worker1", state, worker_context)
        
        # Create thread
        thread_id = f"thread_{uuid.uuid4().hex[:8]}"
        assert manager.create_thread(thread_id, "execution")
        
        # Worker subscribes to thread
        worker.subscribe_to_thread(thread_id)
        
        # Create and assign task
        task = Task.create(
            content="Thread-based task",
            created_by="thread_manager"
        )
        # Dynamically assign to worker for testing
        task.__dict__['assigned_to'] = "worker1"
        
        assert manager.assign_task_to_thread(task, thread_id)
        
        # Worker processes messages
        messages = worker.process_messages()
        assert len(messages["tasks"]) == 1
        assert len(messages["events"]) == 1  # thread_created event
        assert messages["tasks"][0].thread_id == thread_id
        
        # Execute task
        results = worker.execute_tasks(simulate_work=False)
        assert len(results) == 1
        assert thread_id in results[0].metadata["thread_id"]
        
        # Close thread
        assert manager.close_thread(thread_id)
        thread_status = manager.get_thread_status(thread_id)
        assert thread_status["status"] == "closed"
    
    def test_multiple_threads_coordination(self):
        """Test coordination across multiple threads."""
        state = create_test_state_view()
        
        manager_context = create_test_step_context("thread_manager", ["worker1", "worker2"])
        worker1_context = create_test_step_context("worker1", ["thread_manager"])
        worker2_context = create_test_step_context("worker2", ["thread_manager"])
        
        manager = ThreadManager("thread_manager", state, manager_context)
        worker1 = ThreadAwareWorker("worker1", state, worker1_context)
        worker2 = ThreadAwareWorker("worker2", state, worker2_context)
        
        # Create multiple threads
        thread_ids = [f"thread_{i}" for i in range(3)]
        for thread_id in thread_ids:
            assert manager.create_thread(thread_id, "parallel_execution")
        
        # Workers subscribe to different threads
        worker1.subscribe_to_thread(thread_ids[0])
        worker1.subscribe_to_thread(thread_ids[1])
        worker2.subscribe_to_thread(thread_ids[1])
        worker2.subscribe_to_thread(thread_ids[2])
        
        # Assign tasks to threads
        tasks = []
        for i, thread_id in enumerate(thread_ids):
            for j in range(2):  # 2 tasks per thread
                task = Task.create(
                    content=f"Task {i}-{j}",
                    created_by="thread_manager"
                )
                # Dynamically assign to worker for testing
                task.__dict__['assigned_to'] = "worker1" if j == 0 else "worker2"
                tasks.append(task)
                assert manager.assign_task_to_thread(task, thread_id)
        
        # Process messages
        worker1_messages = worker1.process_messages()
        worker2_messages = worker2.process_messages()
        
        # Verify task distribution
        worker1_tasks = worker1_messages["tasks"]
        worker2_tasks = worker2_messages["tasks"]
        
        assert len(worker1_tasks) == 3  # Tasks from thread 0 and 1
        assert len(worker2_tasks) == 3  # Tasks from thread 1 and 2
        
        # Execute tasks
        worker1_results = worker1.execute_tasks(simulate_work=False)
        worker2_results = worker2.execute_tasks(simulate_work=False)
        
        assert len(worker1_results) == 3
        assert len(worker2_results) == 3
        
        # Verify thread context in results
        all_results = worker1_results + worker2_results
        thread_ids_in_results = {r.metadata["thread_id"] for r in all_results}
        assert thread_ids_in_results == set(thread_ids)
    
    def test_thread_workspace_sharing(self):
        """Test workspace data sharing between thread participants."""
        state = create_test_state_view()
        
        manager_context = create_test_step_context("thread_manager", ["worker1", "worker2"])
        worker1_context = create_test_step_context("worker1", ["thread_manager"])
        worker2_context = create_test_step_context("worker2", ["thread_manager"])
        
        manager = ThreadManager("thread_manager", state, manager_context)
        worker1 = ThreadAwareWorker("worker1", state, worker1_context)
        worker2 = ThreadAwareWorker("worker2", state, worker2_context)
        
        # Create thread
        thread_id = "shared_workspace_thread"
        assert manager.create_thread(thread_id, "collaborative")
        
        # Workers subscribe
        worker1.subscribe_to_thread(thread_id)
        worker2.subscribe_to_thread(thread_id)
        
        # Update workspace with initial data
        initial_data = {"counter": 0, "shared_state": "initialized"}
        assert manager.update_thread_workspace(thread_id, initial_data)
        
        # Workers process initial messages
        worker1.process_messages()
        worker2.process_messages()
        
        # Update workspace again
        updated_data = {"counter": 5, "additional_info": "updated"}
        assert manager.update_thread_workspace(thread_id, updated_data)
        
        # Workers process workspace updates
        worker1.process_messages()
        worker2.process_messages()
        
        # Verify workspace data is available to workers
        assert thread_id in worker1.thread_workspaces
        assert thread_id in worker2.thread_workspaces
        
        workspace1 = worker1.thread_workspaces[thread_id]["data"]
        workspace2 = worker2.thread_workspaces[thread_id]["data"]
        
        # Both workers should have the same workspace data
        assert workspace1["counter"] == 5
        assert workspace1["shared_state"] == "initialized"
        assert workspace1["additional_info"] == "updated"
        
        # Compare workspaces without timestamp (which may differ slightly)
        workspace1_without_ts = {k: v for k, v in workspace1.items() if k != "timestamp"}
        workspace2_without_ts = {k: v for k, v in workspace2.items() if k != "timestamp"}
        assert workspace1_without_ts == workspace2_without_ts
        
        # Assign tasks that use workspace data
        task1 = Task.create(
            content="Use workspace data",
            created_by="thread_manager"
        )
        # Dynamically assign to worker for testing
        task1.__dict__['assigned_to'] = "worker1"
        
        task2 = Task.create(
            content="Also use workspace data",
            created_by="thread_manager"
        )
        # Dynamically assign to worker for testing
        task2.__dict__['assigned_to'] = "worker2"
        
        manager.assign_task_to_thread(task1, thread_id)
        manager.assign_task_to_thread(task2, thread_id)
        
        # Process and execute tasks
        worker1.process_messages()
        worker2.process_messages()
        
        results1 = worker1.execute_tasks(simulate_work=False)
        results2 = worker2.execute_tasks(simulate_work=False)
        
        # Verify workspace data is included in results
        assert len(results1) == 1
        assert len(results2) == 1
        
        assert "workspace_data" in results1[0].metadata
        assert "workspace_data" in results2[0].metadata
        
        assert results1[0].metadata["workspace_data"]["counter"] == 5
        assert results2[0].metadata["workspace_data"]["counter"] == 5
    
    def test_concurrent_thread_operations(self):
        """Test thread operations under concurrent access."""
        state = create_test_state_view()
        
        manager_context = create_test_step_context("thread_manager", ["worker1", "worker2", "worker3"])
        worker_contexts = [
            create_test_step_context(f"worker{i}", ["thread_manager"]) 
            for i in range(1, 4)
        ]
        
        manager = ThreadManager("thread_manager", state, manager_context)
        workers = [
            ThreadAwareWorker(f"worker{i}", state, worker_contexts[i-1]) 
            for i in range(1, 4)
        ]
        
        # Create multiple threads concurrently
        def create_threads():
            thread_ids = []
            for i in range(5):
                thread_id = f"concurrent_thread_{threading.current_thread().ident}_{i}"
                if manager.create_thread(thread_id, "concurrent"):
                    thread_ids.append(thread_id)
                time.sleep(0.001)
            return thread_ids
        
        # Start multiple thread creation operations
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_results = [executor.submit(create_threads) for _ in range(3)]
            all_thread_ids = []
            for future in as_completed(future_results):
                all_thread_ids.extend(future.result())
        
        # Verify all threads were created
        all_threads = manager.get_all_threads()
        assert len(all_threads) >= 10  # Should have created at least 10 threads
        
        # Subscribe workers to random threads
        for worker in workers:
            for thread_id in all_thread_ids[:5]:  # Subscribe to first 5 threads
                worker.subscribe_to_thread(thread_id)
        
        # Assign tasks concurrently
        def assign_tasks(thread_batch):
            for thread_id in thread_batch:
                for i in range(3):
                    task = Task.create(
                        content=f"Concurrent task {i} for {thread_id}",
                        created_by="thread_manager"
                    )
                    # Dynamically assign to worker for testing
                    task.__dict__['assigned_to'] = f"worker{(i % 3) + 1}"
                    manager.assign_task_to_thread(task, thread_id)
                    time.sleep(0.001)
        
        # Split threads into batches for concurrent assignment
        batch_size = len(all_thread_ids) // 3
        thread_batches = [
            all_thread_ids[i:i + batch_size] 
            for i in range(0, len(all_thread_ids), batch_size)
        ]
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(assign_tasks, batch) for batch in thread_batches if batch]
            for future in as_completed(futures):
                future.result()  # Wait for completion
        
        # Workers process messages and execute tasks
        def worker_processing(worker):
            messages = worker.process_messages()
            results = worker.execute_tasks(simulate_work=False)
            return len(messages["tasks"]), len(results)
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            worker_futures = [executor.submit(worker_processing, worker) for worker in workers]
            total_tasks_processed = 0
            total_results = 0
            
            for future in as_completed(worker_futures):
                tasks_count, results_count = future.result()
                total_tasks_processed += tasks_count
                total_results += results_count
        
        # Verify significant work was done
        assert total_tasks_processed > 0
        assert total_results > 0
        assert total_tasks_processed == total_results
    
    def test_thread_lifecycle_with_performance_monitoring(self):
        """Test complete thread lifecycle with performance monitoring."""
        state = create_test_state_view()
        monitor = IEMPerformanceMonitor()
        
        manager_context = create_test_step_context("thread_manager", ["worker1"])
        worker_context = create_test_step_context("worker1", ["thread_manager"])
        
        manager = ThreadManager("thread_manager", state, manager_context)
        worker = ThreadAwareWorker("worker1", state, worker_context)
        
        # Monitor thread creation
        with monitor.monitor_operation("thread_creation") as op_id:
            thread_ids = []
            for i in range(10):
                thread_id = f"perf_thread_{i}"
                assert manager.create_thread(thread_id, "performance_test")
                thread_ids.append(thread_id)
        
        # Monitor worker subscription and setup
        with monitor.monitor_operation("worker_setup") as op_id:
            for thread_id in thread_ids:
                worker.subscribe_to_thread(thread_id)
        
        # Monitor task assignment
        with monitor.monitor_operation("task_assignment") as op_id:
            tasks = []
            for i, thread_id in enumerate(thread_ids):
                for j in range(5):  # 5 tasks per thread
                    task = Task.create(
                        content=f"Performance task {i}-{j}",
                        created_by="thread_manager"
                    )
                    # Dynamically assign to worker for testing
                    task.__dict__['assigned_to'] = "worker1"
                    tasks.append(task)
                    assert manager.assign_task_to_thread(task, thread_id)
        
        # Monitor message processing
        with monitor.monitor_operation("message_processing") as op_id:
            messages = worker.process_messages()
        
        # Monitor task execution
        with monitor.monitor_operation("task_execution") as op_id:
            results = worker.execute_tasks(simulate_work=True)
        
        # Monitor thread cleanup
        with monitor.monitor_operation("thread_cleanup") as op_id:
            for thread_id in thread_ids:
                assert manager.close_thread(thread_id)
        
        # Verify performance metrics
        creation_stats = monitor.get_operation_stats("thread_creation")
        setup_stats = monitor.get_operation_stats("worker_setup")
        assignment_stats = monitor.get_operation_stats("task_assignment")
        processing_stats = monitor.get_operation_stats("message_processing")
        execution_stats = monitor.get_operation_stats("task_execution")
        cleanup_stats = monitor.get_operation_stats("thread_cleanup")
        
        # All operations should have succeeded
        assert creation_stats["success_count"] == 1
        assert setup_stats["success_count"] == 1
        assert assignment_stats["success_count"] == 1
        assert processing_stats["success_count"] == 1
        assert execution_stats["success_count"] == 1
        assert cleanup_stats["success_count"] == 1
        
        # Verify work was completed
        assert len(messages["tasks"]) == 50  # 10 threads * 5 tasks
        assert len(messages["events"]) == 10  # 10 thread creation events
        assert len(results) == 50
        
        # Verify thread states
        all_threads = manager.get_all_threads()
        assert len(all_threads) == 10
        assert all(thread["status"] == "closed" for thread in all_threads.values())
    
    def test_thread_error_handling_and_recovery(self):
        """Test thread management with error scenarios."""
        state = create_test_state_view()
        
        manager_context = create_test_step_context("thread_manager", ["worker1", "worker2"])
        worker1_context = create_test_step_context("worker1", ["thread_manager"])
        worker2_context = create_test_step_context("worker2", ["thread_manager"])
        
        manager = ThreadManager("thread_manager", state, manager_context)
        worker1 = ThreadAwareWorker("worker1", state, worker1_context)
        worker2 = ThreadAwareWorker("worker2", state, worker2_context)
        
        # Create threads
        normal_thread = "normal_thread"
        error_thread = "error_thread"
        
        assert manager.create_thread(normal_thread, "normal")
        assert manager.create_thread(error_thread, "error_prone")
        
        # Workers subscribe
        worker1.subscribe_to_thread(normal_thread)
        worker1.subscribe_to_thread(error_thread)
        worker2.subscribe_to_thread(normal_thread)
        
        # Assign tasks
        normal_task = Task.create(
            content="Normal task",
            created_by="thread_manager"
        )
        # Dynamically assign to worker for testing
        normal_task.__dict__['assigned_to'] = "worker1"
        
        error_task = Task.create(
            content="Task that will error",
            created_by="thread_manager",
            data={"simulate_error": True}
        )
        # Dynamically assign to worker for testing
        error_task.__dict__['assigned_to'] = "worker1"
        
        backup_task = Task.create(
            content="Backup task for recovery",
            created_by="thread_manager"
        )
        # Dynamically assign to worker for testing
        backup_task.__dict__['assigned_to'] = "worker2"
        
        assert manager.assign_task_to_thread(normal_task, normal_thread)
        assert manager.assign_task_to_thread(error_task, error_thread)
        assert manager.assign_task_to_thread(backup_task, normal_thread)
        
        # Process messages
        worker1.process_messages()
        worker2.process_messages()
        
        # Worker1 simulates partial failure
        worker1_results = []
        with worker1.lock:
            tasks_to_process = list(worker1.processing_tasks.items())
        
        for task_id, task_info in tasks_to_process:
            task = task_info["task"]
            
            if task.data and task.data.get("simulate_error"):
                # Simulate error
                error_result = AgentResult(
                    task_id=task.task_id,
                    agent_id="worker1",
                    status=TaskStatus.FAILED,
                    output="Task failed",
                    error="Simulated error in thread processing"
                )
                
                task.result = error_result.__dict__
                task.__dict__['status'] = TaskStatus.FAILED
                task.error = "Simulated error"
                
                response_packet = TaskPacket.create(
                    src=ElementAddress(uid="worker1"),
                    dst=ElementAddress(uid=task.created_by),
                    task=task
                )
                
                worker1.messenger.send_packet(response_packet)
                worker1_results.append(error_result)
            else:
                # Process normally
                result = AgentResult(
                    task_id=task.task_id,
                    agent_id="worker1",
                    status=TaskStatus.COMPLETED,
                    output=f"Processed: {task.content}",
                    metadata={"thread_id": task.thread_id}
                )
                
                task.result = result.__dict__
                task.__dict__['status'] = TaskStatus.COMPLETED
                
                response_packet = TaskPacket.create(
                    src=ElementAddress(uid="worker1"),
                    dst=ElementAddress(uid=task.created_by),
                    task=task
                )
                
                worker1.messenger.send_packet(response_packet)
                worker1_results.append(result)
            
            with worker1.lock:
                worker1.processing_tasks.pop(task_id, None)
        
        # Worker2 processes normally
        worker2_results = worker2.execute_tasks(simulate_work=False)
        
        # Verify mixed results
        all_results = worker1_results + worker2_results
        assert len(all_results) == 3
        
        successful_results = [r for r in all_results if r.status == TaskStatus.COMPLETED]
        failed_results = [r for r in all_results if r.status == TaskStatus.FAILED]
        
        assert len(successful_results) == 2  # normal_task + backup_task
        assert len(failed_results) == 1  # error_task
        
        # Verify thread management continues despite errors
        assert manager.close_thread(normal_thread)
        assert manager.close_thread(error_thread)
        
        normal_status = manager.get_thread_status(normal_thread)
        error_status = manager.get_thread_status(error_thread)
        
        assert normal_status["status"] == "closed"
        assert error_status["status"] == "closed"
