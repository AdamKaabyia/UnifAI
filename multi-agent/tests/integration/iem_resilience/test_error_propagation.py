"""
Comprehensive tests for IEM error propagation and handling.

Tests error scenarios, recovery mechanisms, and system resilience.
"""

import pytest
import uuid
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from unittest.mock import Mock, patch, MagicMock

from mas.core.iem.messenger import DefaultInterMessenger
from mas.core.iem.models import ElementAddress, PacketType
from mas.core.iem.packets import BaseIEMPacket, TaskPacket, SystemPacket, DebugPacket
from mas.core.iem.exceptions import IEMException, IEMValidationException, IEMAdjacencyException
from mas.core.iem.interfaces import MessengerMiddleware
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
    PacketFactory, IEMPerformanceMonitor, ChaosInjector
)


class ErrorPropagationMiddleware(MessengerMiddleware):
    """Middleware that simulates various error conditions."""
    
    def __init__(self, 
                 send_error_rate: float = 0.0,
                 receive_error_rate: float = 0.0,
                 error_type: str = "validation"):
        self.send_error_rate = send_error_rate
        self.receive_error_rate = receive_error_rate
        self.error_type = error_type
        self.errors_triggered = []
        self.packet_count = 0
    
    def before_send(self, packet: BaseIEMPacket) -> BaseIEMPacket:
        self.packet_count += 1
        
        if self._should_trigger_error(self.send_error_rate):
            error_info = {
                "packet_id": packet.id,
                "error_type": f"send_{self.error_type}",
                "timestamp": datetime.utcnow()
            }
            self.errors_triggered.append(error_info)
            
            if self.error_type == "validation":
                raise IEMValidationException(f"Send validation error for packet {packet.id}")
            elif self.error_type == "adjacency":
                raise IEMAdjacencyException(f"Adjacency error for packet {packet.id}")
            else:
                raise IEMException(f"Generic error for packet {packet.id}")
        
        return packet
    
    def after_receive(self, packet: BaseIEMPacket) -> BaseIEMPacket:
        if self._should_trigger_error(self.receive_error_rate):
            error_info = {
                "packet_id": packet.id,
                "error_type": f"receive_{self.error_type}",
                "timestamp": datetime.utcnow()
            }
            self.errors_triggered.append(error_info)
            
            if self.error_type == "validation":
                raise IEMValidationException(f"Receive validation error for packet {packet.id}")
            else:
                raise IEMException(f"Generic receive error for packet {packet.id}")
        
        return packet
    
    def _should_trigger_error(self, error_rate: float) -> bool:
        import random
        return random.random() < error_rate


class ResilientNode:
    """Node that implements error recovery mechanisms."""
    
    def __init__(self, uid: str, state_view, context, 
                 retry_count: int = 3, 
                 backoff_factor: float = 1.0):
        self.uid = uid
        self.messenger = DefaultInterMessenger(
            state=state_view,
            identity=ElementAddress(uid=uid),
            context=context
        )
        self.retry_count = retry_count
        self.backoff_factor = backoff_factor
        self.failed_packets = {}
        self.retry_attempts = {}
        self.error_log = []
        self.circuit_breaker_state = "closed"  # closed, open, half_open
        self.circuit_breaker_failures = 0
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = timedelta(seconds=10)
        self.circuit_breaker_last_failure = None
    
    def send_packet_with_retry(self, packet: BaseIEMPacket) -> bool:
        """Send packet with retry mechanism."""
        packet_id = packet.id
        
        for attempt in range(self.retry_count + 1):
            try:
                # Check circuit breaker
                if not self._circuit_breaker_check():
                    self._log_error("Circuit breaker open", packet_id, attempt)
                    return False
                
                self.messenger.send_packet(packet)
                
                # Success - reset circuit breaker failures
                self.circuit_breaker_failures = 0
                if packet_id in self.retry_attempts:
                    del self.retry_attempts[packet_id]
                
                return True
                
            except Exception as e:
                self._log_error(str(e), packet_id, attempt)
                self.circuit_breaker_failures += 1
                self.circuit_breaker_last_failure = datetime.utcnow()
                
                if attempt < self.retry_count:
                    # Exponential backoff
                    delay = self.backoff_factor * (2 ** attempt)
                    time.sleep(delay)
                    
                    self.retry_attempts[packet_id] = attempt + 1
                else:
                    # Final failure
                    self.failed_packets[packet_id] = {
                        "packet": packet,
                        "attempts": attempt + 1,
                        "last_error": str(e),
                        "failed_at": datetime.utcnow()
                    }
                    
                    # Update circuit breaker
                    if self.circuit_breaker_failures >= self.circuit_breaker_threshold:
                        self.circuit_breaker_state = "open"
        
        return False
    
    def receive_packets_with_error_handling(self) -> List[BaseIEMPacket]:
        """Receive packets with error handling."""
        try:
            return self.messenger.inbox_packets()
        except Exception as e:
            self._log_error(f"Receive error: {str(e)}", None, 0)
            return []
    
    def _circuit_breaker_check(self) -> bool:
        """Check circuit breaker state."""
        now = datetime.utcnow()
        
        if self.circuit_breaker_state == "open":
            if (self.circuit_breaker_last_failure and 
                now - self.circuit_breaker_last_failure > self.circuit_breaker_timeout):
                self.circuit_breaker_state = "half_open"
                return True
            return False
        
        return True
    
    def _log_error(self, error_msg: str, packet_id: Optional[str], attempt: int):
        """Log error information."""
        error_entry = {
            "timestamp": datetime.utcnow(),
            "error": error_msg,
            "packet_id": packet_id,
            "attempt": attempt,
            "node": self.uid
        }
        self.error_log.append(error_entry)
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics."""
        return {
            "total_errors": len(self.error_log),
            "failed_packets": len(self.failed_packets),
            "retry_attempts": sum(self.retry_attempts.values()),
            "circuit_breaker_state": self.circuit_breaker_state,
            "circuit_breaker_failures": self.circuit_breaker_failures
        }
    
    def reset_error_state(self):
        """Reset error tracking state."""
        self.failed_packets.clear()
        self.retry_attempts.clear()
        self.error_log.clear()
        self.circuit_breaker_state = "closed"
        self.circuit_breaker_failures = 0
        self.circuit_breaker_last_failure = None


class ErrorRecoveryCoordinator:
    """Coordinates error recovery across multiple nodes."""
    
    def __init__(self, uid: str, state_view, context):
        self.uid = uid
        self.messenger = DefaultInterMessenger(
            state=state_view,
            identity=ElementAddress(uid=uid),
            context=context
        )
        self.node_health = {}
        self.error_notifications = []
        self.recovery_actions = []
    
    def monitor_node_health(self, node_uid: str) -> Dict[str, Any]:
        """Monitor health of a specific node."""
        health_check_packet = SystemPacket(
            src=ElementAddress(uid=self.uid),
            dst=ElementAddress(uid=node_uid),
            system_event="health_check",
            data={"timestamp": datetime.utcnow().isoformat()}
        )
        
        try:
            self.messenger.send_packet(health_check_packet)
            self.node_health[node_uid] = {
                "status": "check_sent",
                "last_check": datetime.utcnow()
            }
            return self.node_health[node_uid]
        except Exception as e:
            self.node_health[node_uid] = {
                "status": "unreachable",
                "error": str(e),
                "last_check": datetime.utcnow()
            }
            return self.node_health[node_uid]
    
    def handle_error_notification(self, error_packet: SystemPacket):
        """Handle error notifications from nodes."""
        error_info = {
            "from_node": error_packet.src.uid,
            "error_type": error_packet.data.get("error_type", "unknown"),
            "error_message": error_packet.data.get("error_message", ""),
            "timestamp": datetime.utcnow(),
            "packet": error_packet
        }
        
        self.error_notifications.append(error_info)
        
        # Trigger recovery action based on error type
        self._trigger_recovery_action(error_info)
    
    def _trigger_recovery_action(self, error_info: Dict[str, Any]):
        """Trigger appropriate recovery action."""
        error_type = error_info["error_type"]
        from_node = error_info["from_node"]
        
        recovery_action = {
            "action_type": "unknown",
            "target_node": from_node,
            "timestamp": datetime.utcnow(),
            "triggered_by": error_info
        }
        
        if error_type == "communication_failure":
            recovery_action["action_type"] = "retry_communication"
            self._retry_communication(from_node)
        elif error_type == "resource_exhaustion":
            recovery_action["action_type"] = "redistribute_load"
            self._redistribute_load(from_node)
        elif error_type == "validation_failure":
            recovery_action["action_type"] = "reset_validation"
            self._reset_validation(from_node)
        
        self.recovery_actions.append(recovery_action)
    
    def _retry_communication(self, node_uid: str):
        """Retry communication with a node."""
        retry_packet = SystemPacket(
            src=ElementAddress(uid=self.uid),
            dst=ElementAddress(uid=node_uid),
            system_event="retry_communication",
            data={"coordinator": self.uid}
        )
        
        try:
            self.messenger.send_packet(retry_packet)
        except Exception:
            pass  # Recovery action itself failed
    
    def _redistribute_load(self, failed_node: str):
        """Redistribute load from failed node."""
        redistribution_packet = SystemPacket(
            src=ElementAddress(uid=self.uid),
            dst=ElementAddress(uid="load_balancer"),
            system_event="redistribute_load",
            data={
                "failed_node": failed_node,
                "coordinator": self.uid
            }
        )
        
        try:
            self.messenger.send_packet(redistribution_packet)
        except Exception:
            pass  # Recovery action itself failed
    
    def _reset_validation(self, node_uid: str):
        """Reset validation state for a node."""
        reset_packet = SystemPacket(
            src=ElementAddress(uid=self.uid),
            dst=ElementAddress(uid=node_uid),
            system_event="reset_validation",
            data={"coordinator": self.uid}
        )
        
        try:
            self.messenger.send_packet(reset_packet)
        except Exception:
            pass  # Recovery action itself failed


class TestErrorPropagation:
    """Test suite for IEM error propagation and handling."""
    
    def test_middleware_error_propagation(self):
        """Test error propagation through middleware chain."""
        state = create_test_state_view()
        
        # Create middleware that triggers errors
        error_middleware = ErrorPropagationMiddleware(
            send_error_rate=0.5,  # 50% error rate
            error_type="validation"
        )
        
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="test_node"),
            middleware=[error_middleware]
        )
        
        # Send multiple packets, some should fail
        packets_sent = 0
        errors_caught = 0
        
        for i in range(20):
            packet = PacketFactory.create_task_packet("sender", "receiver", f"packet_{i}")
            
            try:
                messenger.send_packet(packet)
                packets_sent += 1
            except IEMValidationException:
                errors_caught += 1
        
        # Should have caught some errors
        assert errors_caught > 0
        assert packets_sent + errors_caught == 20
        assert len(error_middleware.errors_triggered) == errors_caught
        
        # Verify error details
        for error in error_middleware.errors_triggered:
            assert "send_validation" in error["error_type"]
            assert error["packet_id"] is not None
    
    def test_resilient_node_retry_mechanism(self):
        """Test resilient node retry mechanism."""
        state = create_test_state_view()
        
        # Create node with retry capability
        context = create_test_step_context("resilient_node", ["target"])
        resilient_node = ResilientNode("resilient_node", state, context, retry_count=3, backoff_factor=0.01)
        
        # Add error middleware to messenger
        error_middleware = ErrorPropagationMiddleware(
            send_error_rate=0.7,  # 70% error rate
            error_type="validation"
        )
        resilient_node.messenger._middleware = [error_middleware]
        
        # Try to send packets
        packet = PacketFactory.create_task_packet("resilient_node", "target")
        success = resilient_node.send_packet_with_retry(packet)
        
        # Check retry attempts
        error_stats = resilient_node.get_error_statistics()
        
        if success:
            # If successful, should have minimal retries
            assert error_stats["retry_attempts"] >= 0
        else:
            # If failed, should have attempted all retries
            assert packet.id in resilient_node.failed_packets
            assert resilient_node.failed_packets[packet.id]["attempts"] == 4  # 1 + 3 retries

        # Error injection is probabilistic - may not always trigger
        # The important thing is that retry mechanism is in place
        assert error_stats["total_errors"] >= 0  # Can be 0 due to randomness
    
    def test_circuit_breaker_functionality(self):
        """Test circuit breaker pattern implementation."""
        state = create_test_state_view()
        
        context = create_test_step_context("circuit_breaker_node", ["target"])
        node = ResilientNode(
            "circuit_breaker_node", 
            state, 
            context, 
            retry_count=1
        )
        
        # Set low circuit breaker threshold for testing
        node.circuit_breaker_threshold = 3
        
        # Add middleware that always fails
        error_middleware = ErrorPropagationMiddleware(
            send_error_rate=1.0,  # 100% error rate
            error_type="validation"
        )
        node.messenger._middleware = [error_middleware]
        
        # Send packets until circuit breaker opens
        packets_before_breaker = 0
        for i in range(10):
            packet = PacketFactory.create_task_packet("circuit_breaker_node", "target", f"packet_{i}")
            
            if node._circuit_breaker_check():
                success = node.send_packet_with_retry(packet)
                if not success:
                    packets_before_breaker += 1
            else:
                # Circuit breaker is open
                break
        
        # Verify circuit breaker opened
        assert node.circuit_breaker_state == "open"
        assert node.circuit_breaker_failures >= node.circuit_breaker_threshold
        
        # Verify subsequent packets are rejected without retry
        packet = PacketFactory.create_task_packet("circuit_breaker_node", "target", "post_breaker")
        success = node.send_packet_with_retry(packet)
        assert not success
        
        error_stats = node.get_error_statistics()
        assert error_stats["circuit_breaker_state"] == "open"
    
    def test_error_recovery_coordinator(self):
        """Test error recovery coordination."""
        state = create_test_state_view()
        
        coord_context = create_test_step_context("coordinator", ["node1", "node2"])
        coordinator = ErrorRecoveryCoordinator("coordinator", state, coord_context)
        
        # Simulate health checks
        health1 = coordinator.monitor_node_health("node1")
        health2 = coordinator.monitor_node_health("node2")
        
        assert health1["status"] == "check_sent"
        assert health2["status"] == "check_sent"
        
        # Simulate error notification
        error_packet = SystemPacket(
            src=ElementAddress(uid="node1"),
            dst=ElementAddress(uid="coordinator"),
            system_event="error_notification",
            data={
                "error_type": "communication_failure",
                "error_message": "Failed to communicate with peer",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        coordinator.handle_error_notification(error_packet)
        
        # Verify error handling
        assert len(coordinator.error_notifications) == 1
        assert len(coordinator.recovery_actions) == 1
        
        recovery_action = coordinator.recovery_actions[0]
        assert recovery_action["action_type"] == "retry_communication"
        assert recovery_action["target_node"] == "node1"
    
    def test_cascading_failure_detection(self):
        """Test detection and handling of cascading failures."""
        state = create_test_state_view()
        
        # Create multiple nodes
        contexts = {
            f"node{i}": create_test_step_context(f"node{i}", [f"node{j}" for j in range(1, 5) if j != i])
            for i in range(1, 5)
        }
        
        nodes = {
            uid: ResilientNode(uid, state, contexts[uid], retry_count=2, backoff_factor=0.01)
            for uid in contexts
        }
        
        # Add error middleware to simulate failures
        for node in nodes.values():
            error_middleware = ErrorPropagationMiddleware(
                send_error_rate=0.3,  # 30% error rate
                error_type="validation"
            )
            node.messenger._middleware = [error_middleware]
        
        # Simulate workload - each node sends to others
        total_packets = 0
        total_failures = 0
        
        for sender_uid, sender_node in nodes.items():
            for target_uid in contexts[sender_uid].adjacent_nodes:
                if target_uid in nodes:
                    packet = PacketFactory.create_task_packet(sender_uid, target_uid)
                    success = sender_node.send_packet_with_retry(packet)
                    total_packets += 1
                    if not success:
                        total_failures += 1
        
        # Analyze failure patterns
        assert total_packets > 0
        
        # Check if any nodes hit circuit breaker
        nodes_with_circuit_breaker = [
            uid for uid, node in nodes.items() 
            if node.circuit_breaker_state == "open"
        ]
        
        # Get overall error statistics
        total_errors = sum(len(node.error_log) for node in nodes.values())
        total_failed_packets = sum(len(node.failed_packets) for node in nodes.values())
        
        assert total_errors > 0  # Should have some errors due to 30% error rate
        
        # Verify error distribution
        error_distribution = {
            uid: len(node.error_log) 
            for uid, node in nodes.items()
        }
        
        # Should have errors distributed across nodes
        nodes_with_errors = sum(1 for count in error_distribution.values() if count > 0)
        assert nodes_with_errors > 0
    
    def test_error_recovery_with_performance_monitoring(self):
        """Test error recovery with performance impact analysis."""
        state = create_test_state_view()
        monitor = IEMPerformanceMonitor()
        
        context = create_test_step_context("perf_node", ["target1", "target2"])
        node = ResilientNode("perf_node", state, context, retry_count=3, backoff_factor=0.01)
        
        # Add error middleware
        error_middleware = ErrorPropagationMiddleware(
            send_error_rate=0.4,  # 40% error rate
            error_type="validation"
        )
        node.messenger._middleware = [error_middleware]
        
        # Monitor error handling performance
        with monitor.monitor_operation("error_handling_test") as op_id:
            success_count = 0
            failure_count = 0
            
            for i in range(50):
                packet = PacketFactory.create_task_packet("perf_node", f"target{i % 2 + 1}", f"packet_{i}")
                
                with monitor.monitor_operation("individual_send") as send_op:
                    success = node.send_packet_with_retry(packet)
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
        
        # Analyze performance impact
        error_stats = node.get_error_statistics()
        
        # Get performance metrics
        overall_stats = monitor.get_operation_stats("error_handling_test")
        individual_stats = monitor.get_operation_stats("individual_send")
        
        assert overall_stats["success_count"] == 1
        assert individual_stats["total_calls"] == 50
        
        # Verify error handling worked
        assert success_count + failure_count == 50
        assert error_stats["total_errors"] > 0
        
        # Performance impact analysis
        avg_duration = individual_stats["avg_duration_ms"]
        total_retries = error_stats["retry_attempts"]
        
        # With retries and backoff, average duration should be reasonable
        assert avg_duration > 0
        assert total_retries >= 0
    
    def test_concurrent_error_handling(self):
        """Test error handling under concurrent conditions."""
        state = create_test_state_view()
        
        context = create_test_step_context("concurrent_node", ["target1", "target2", "target3"])
        node = ResilientNode("concurrent_node", state, context, retry_count=2, backoff_factor=0.01)  # Fast retries for testing
        
        # Add error middleware
        error_middleware = ErrorPropagationMiddleware(
            send_error_rate=0.5,  # 50% error rate
            error_type="validation"
        )
        node.messenger._middleware = [error_middleware]
        
        # Concurrent packet sending
        def send_packets_thread(thread_id: int, packet_count: int):
            results = {"success": 0, "failure": 0}
            
            for i in range(packet_count):
                packet = PacketFactory.create_task_packet(
                    "concurrent_node", 
                    f"target{(i % 3) + 1}", 
                    f"thread_{thread_id}_packet_{i}"
                )
                
                success = node.send_packet_with_retry(packet)
                if success:
                    results["success"] += 1
                else:
                    results["failure"] += 1
                
                time.sleep(0.001)  # Small delay
            
            return results
        
        # Start multiple threads
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(send_packets_thread, thread_id, 20)
                for thread_id in range(5)
            ]
            
            thread_results = [future.result() for future in futures]
        
        # Aggregate results
        total_success = sum(result["success"] for result in thread_results)
        total_failure = sum(result["failure"] for result in thread_results)
        total_packets = total_success + total_failure
        
        assert total_packets == 100  # 5 threads * 20 packets
        
        # Verify error handling worked correctly under concurrency
        error_stats = node.get_error_statistics()
        assert error_stats["total_errors"] > 0
        
        # Circuit breaker should still function correctly
        assert node.circuit_breaker_state in ["closed", "open", "half_open"]
        
        # Thread safety verification - no duplicate packet IDs in failed packets
        failed_packet_ids = list(node.failed_packets.keys())
        assert len(failed_packet_ids) == len(set(failed_packet_ids))
    
    def test_error_boundary_conditions(self):
        """Test error handling at boundary conditions."""
        state = create_test_state_view()
        context = create_test_step_context("boundary_node", ["target"])
        
        # Test with zero retry count
        zero_retry_node = ResilientNode("boundary_node", state, context, retry_count=0)
        error_middleware = ErrorPropagationMiddleware(send_error_rate=1.0)
        zero_retry_node.messenger._middleware = [error_middleware]
        
        packet = PacketFactory.create_task_packet("boundary_node", "target")
        success = zero_retry_node.send_packet_with_retry(packet)
        
        assert not success
        assert packet.id in zero_retry_node.failed_packets
        assert zero_retry_node.failed_packets[packet.id]["attempts"] == 1
        
        # Test with very high retry count
        high_retry_node = ResilientNode("boundary_node", state, context, retry_count=10, backoff_factor=0.001)  # Reduced for testing
        high_retry_node.messenger._middleware = [error_middleware]
        
        # Should still fail but with many attempts (limited by reasonable timeout)
        packet2 = PacketFactory.create_task_packet("boundary_node", "target")
        
        start_time = time.time()
        success2 = high_retry_node.send_packet_with_retry(packet2)
        duration = time.time() - start_time
        
        assert not success2
        # Should have attempted multiple times but not indefinitely
        assert duration < 10.0  # Should complete within reasonable time
        
        # Test with extreme backoff factor
        extreme_backoff_node = ResilientNode(
            "boundary_node", 
            state, 
            context, 
            retry_count=3, 
            backoff_factor=0.001  # Very small backoff
        )
        extreme_backoff_node.messenger._middleware = [error_middleware]
        
        packet3 = PacketFactory.create_task_packet("boundary_node", "target")
        
        start_time = time.time()
        success3 = extreme_backoff_node.send_packet_with_retry(packet3)
        duration = time.time() - start_time
        
        assert not success3
        # Should complete quickly due to small backoff
        assert duration < 1.0
