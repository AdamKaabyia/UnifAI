"""
Integration tests for two-node IEM communication.

Tests basic communication patterns between two nodes including
task delegation, bidirectional communication, and request-response patterns.
"""

import pytest
import time
from datetime import timedelta

from mas.core.iem.messenger import DefaultInterMessenger
from mas.core.iem.models import ElementAddress, PacketType
from mas.graph.state.graph_state import Channel
from tests.fixtures.iem_testing_tools import (
    PacketFactory, create_test_state_view, create_test_step_context,
    MockIEMNode, IEMPerformanceMonitor
)


class TestTwoNodeCommunication:
    """Test suite for two-node IEM communication patterns."""
    
    def test_simple_task_delegation(self):
        """Test simple task delegation from one node to another."""
        # Setup shared state
        state = create_test_state_view()
        
        # Create nodes with adjacency
        delegator_context = create_test_step_context(
            uid="delegator",
            adjacent_nodes=["worker"]
        )
        worker_context = create_test_step_context(
            uid="worker",
            adjacent_nodes=["delegator"]
        )
        
        delegator = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="delegator"),
            context=delegator_context
        )
        
        worker = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="worker"),
            context=worker_context
        )
        
        # Delegator sends task to worker
        task_packet = PacketFactory.create_task_packet(
            src_uid="delegator",
            dst_uid="worker",
            task_content="Process data batch",
            thread_id="thread_123"
        )
        
        packet_id = delegator.send_packet(task_packet)
        assert packet_id == task_packet.id
        
        # Worker receives task
        worker_inbox = worker.inbox_packets(PacketType.TASK)
        assert len(worker_inbox) == 1
        
        received_task = worker_inbox[0]
        assert received_task.src.uid == "delegator"
        assert received_task.dst.uid == "worker"
        
        # Verify task content
        task = received_task.extract_task()
        assert task.content == "Process data batch"
        assert task.thread_id == "thread_123"
        
        # Worker acknowledges task
        ack_result = worker.acknowledge(received_task.id)
        assert ack_result is True
        
        # Verify task is no longer in worker's inbox
        worker_inbox_after = worker.inbox_packets()
        assert len(worker_inbox_after) == 0
        
    def test_bidirectional_communication(self):
        """Test bidirectional communication between two nodes."""
        state = create_test_state_view()
        
        # Create nodes with mutual adjacency
        node_a_context = create_test_step_context(
            uid="node_a",
            adjacent_nodes=["node_b"]
        )
        node_b_context = create_test_step_context(
            uid="node_b",
            adjacent_nodes=["node_a"]
        )
        
        node_a = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="node_a"),
            context=node_a_context
        )
        
        node_b = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="node_b"),
            context=node_b_context
        )
        
        # Node A sends to Node B
        packet_a_to_b = PacketFactory.create_task_packet(
            src_uid="node_a",
            dst_uid="node_b",
            task_content="Message from A to B"
        )
        node_a.send_packet(packet_a_to_b)
        
        # Node B sends to Node A
        packet_b_to_a = PacketFactory.create_task_packet(
            src_uid="node_b",
            dst_uid="node_a",
            task_content="Message from B to A"
        )
        node_b.send_packet(packet_b_to_a)
        
        # Node A receives from Node B
        node_a_inbox = node_a.inbox_packets()
        assert len(node_a_inbox) == 1
        assert node_a_inbox[0].src.uid == "node_b"
        assert node_a_inbox[0].extract_task().content == "Message from B to A"
        
        # Node B receives from Node A
        node_b_inbox = node_b.inbox_packets()
        assert len(node_b_inbox) == 1
        assert node_b_inbox[0].src.uid == "node_a"
        assert node_b_inbox[0].extract_task().content == "Message from A to B"
        
        # Both nodes acknowledge their received messages
        node_a.acknowledge(node_a_inbox[0].id)
        node_b.acknowledge(node_b_inbox[0].id)
        
        # Verify clean state
        assert len(node_a.inbox_packets()) == 0
        assert len(node_b.inbox_packets()) == 0
        
    def test_request_response_pattern(self):
        """Test request-response pattern between two nodes."""
        state = create_test_state_view()
        
        # Create requester and responder
        requester_context = create_test_step_context(
            uid="requester",
            adjacent_nodes=["responder"]
        )
        responder_context = create_test_step_context(
            uid="responder", 
            adjacent_nodes=["requester"]
        )
        
        requester = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="requester"),
            context=requester_context
        )
        
        responder = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="responder"),
            context=responder_context
        )
        
        # Requester sends request
        request_packet = PacketFactory.create_task_packet(
            src_uid="requester",
            dst_uid="responder",
            task_content="Get user data for ID 12345"
        )
        request_packet.payload["should_respond"] = True
        request_packet.payload["correlation_id"] = "req_001"
        
        requester.send_packet(request_packet)
        
        # Responder receives request
        responder_inbox = responder.inbox_packets()
        assert len(responder_inbox) == 1
        
        request = responder_inbox[0]
        responder.acknowledge(request.id)
        
        # Responder sends response
        response_packet = PacketFactory.create_task_packet(
            src_uid="responder",
            dst_uid="requester",
            task_content="User data: John Doe, email: john@example.com"
        )
        response_packet.payload["correlation_id"] = "req_001"
        response_packet.payload["is_response"] = True
        
        responder.send_packet(response_packet)
        
        # Requester receives response
        requester_inbox = requester.inbox_packets()
        assert len(requester_inbox) == 1
        
        response = requester_inbox[0]
        assert response.src.uid == "responder"
        assert response.payload.get("correlation_id") == "req_001"
        assert response.payload.get("is_response") is True
        
        # Verify response content
        response_task = response.extract_task()
        assert "John Doe" in response_task.content
        
        requester.acknowledge(response.id)
        
    def test_acknowledgment_between_nodes(self):
        """Test acknowledgment behavior between multiple nodes."""
        state = create_test_state_view()
        
        # Create sender and multiple receivers
        sender_context = create_test_step_context(
            uid="sender",
            adjacent_nodes=["receiver_1", "receiver_2"]
        )
        
        sender = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="sender"),
            context=sender_context
        )
        
        receivers = []
        for i in [1, 2]:
            receiver_context = create_test_step_context(
                uid=f"receiver_{i}",
                adjacent_nodes=["sender"]
            )
            receiver = DefaultInterMessenger(
                state=state,
                identity=ElementAddress(uid=f"receiver_{i}"),
                context=receiver_context
            )
            receivers.append(receiver)
            
        # Send packets to both receivers
        packet1 = PacketFactory.create_task_packet(
            src_uid="sender",
            dst_uid="receiver_1",
            task_content="Task for receiver 1"
        )
        packet2 = PacketFactory.create_task_packet(
            src_uid="sender",
            dst_uid="receiver_2", 
            task_content="Task for receiver 2"
        )
        
        sender.send_packet(packet1)
        sender.send_packet(packet2)
        
        # Each receiver gets their packet
        receiver1_inbox = receivers[0].inbox_packets()
        receiver2_inbox = receivers[1].inbox_packets()
        
        assert len(receiver1_inbox) == 1
        assert len(receiver2_inbox) == 1
        assert receiver1_inbox[0].dst.uid == "receiver_1"
        assert receiver2_inbox[0].dst.uid == "receiver_2"
        
        # Only receiver 1 acknowledges
        receivers[0].acknowledge(receiver1_inbox[0].id)
        
        # Receiver 1 should have empty inbox, receiver 2 should still have packet
        assert len(receivers[0].inbox_packets()) == 0
        assert len(receivers[1].inbox_packets()) == 1
        
        # Receiver 2 acknowledges
        receivers[1].acknowledge(receiver2_inbox[0].id)
        
        # Both should have empty inboxes
        assert len(receivers[0].inbox_packets()) == 0
        assert len(receivers[1].inbox_packets()) == 0
        
    def test_communication_with_performance_monitoring(self):
        """Test two-node communication with performance monitoring."""
        state = create_test_state_view()
        monitor = IEMPerformanceMonitor()
        
        # Create nodes
        sender_context = create_test_step_context(
            uid="perf_sender",
            adjacent_nodes=["perf_receiver"]
        )
        receiver_context = create_test_step_context(
            uid="perf_receiver",
            adjacent_nodes=["perf_sender"]
        )
        
        sender = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="perf_sender"),
            context=sender_context
        )
        
        receiver = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="perf_receiver"),
            context=receiver_context
        )
        
        # Monitor complete communication cycle
        with monitor.monitor_operation("send_task") as op_id:
            packet = PacketFactory.create_task_packet(
                src_uid="perf_sender",
                dst_uid="perf_receiver",
                task_content="Performance test task"
            )
            sender.send_packet(packet)
            
        with monitor.monitor_operation("receive_task") as op_id:
            inbox = receiver.inbox_packets()
            assert len(inbox) == 1
            
        with monitor.monitor_operation("acknowledge_task") as op_id:
            receiver.acknowledge(inbox[0].id)
            
        # Verify performance metrics
        send_stats = monitor.get_operation_stats("send_task")
        receive_stats = monitor.get_operation_stats("receive_task")
        ack_stats = monitor.get_operation_stats("acknowledge_task")
        
        # Check that operations were recorded (using correct field names from original implementation)
        assert send_stats["success_count"] == 1
        assert receive_stats["success_count"] == 1
        assert ack_stats["success_count"] == 1
        
        # Verify duration tracking
        assert send_stats["avg_duration_ms"] >= 0
        assert receive_stats["avg_duration_ms"] >= 0
        assert ack_stats["avg_duration_ms"] >= 0
        
        # Verify overall performance
        overall_stats = monitor.get_overall_stats()
        assert overall_stats["total_operations"] == 3
        assert overall_stats["overall_success_rate"] == 1.0
        
    def test_communication_failure_recovery(self):
        """Test communication failure scenarios and recovery."""
        state = create_test_state_view()
        
        # Create nodes with failure simulation
        sender_context = create_test_step_context(
            uid="sender",
            adjacent_nodes=["receiver"]
        )
        
        sender = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="sender"),
            context=sender_context
        )
        
        # Mock receiver that initially fails
        receiver_context = create_test_step_context(
            uid="receiver",
            adjacent_nodes=["sender"]
        )
        
        receiver = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="receiver"),
            context=receiver_context
        )
        
        # Send multiple packets
        packets = []
        for i in range(3):
            packet = PacketFactory.create_task_packet(
                src_uid="sender",
                dst_uid="receiver",
                task_content=f"Task {i+1}"
            )
            sender.send_packet(packet)
            packets.append(packet)
            
        # Receiver acknowledges only first packet (simulating partial failure)
        inbox = receiver.inbox_packets()
        assert len(inbox) == 3
        
        receiver.acknowledge(inbox[0].id)
        
        # Verify partial acknowledgment
        remaining_inbox = receiver.inbox_packets()
        assert len(remaining_inbox) == 2
        
        # Recovery: acknowledge remaining packets
        for packet in remaining_inbox:
            receiver.acknowledge(packet.id)
            
        # Verify full recovery
        final_inbox = receiver.inbox_packets()
        assert len(final_inbox) == 0
        
    def test_communication_with_ttl_expiration(self):
        """Test communication with packet TTL expiration."""
        state = create_test_state_view()
        
        sender_context = create_test_step_context(
            uid="sender",
            adjacent_nodes=["receiver"]
        )
        receiver_context = create_test_step_context(
            uid="receiver",
            adjacent_nodes=["sender"]
        )
        
        sender = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="sender"),
            context=sender_context
        )
        
        receiver = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="receiver"),
            context=receiver_context
        )
        
        # Send packet with short TTL
        packet = PacketFactory.create_task_packet(
            src_uid="sender",
            dst_uid="receiver",
            task_content="Expiring task"
        )
        packet.ttl = timedelta(milliseconds=100)
        
        sender.send_packet(packet)
        
        # Immediate receive should work
        inbox = receiver.inbox_packets()
        assert len(inbox) == 1
        
        # Wait for expiration
        time.sleep(0.2)
        
        # Packet should be expired and not in inbox
        expired_inbox = receiver.inbox_packets()
        assert len(expired_inbox) == 0
        
    def test_complex_two_node_workflow(self):
        """Test complex workflow between two nodes."""
        state = create_test_state_view()
        
        # Create orchestrator and worker
        orchestrator_context = create_test_step_context(
            uid="orchestrator",
            adjacent_nodes=["worker"]
        )
        worker_context = create_test_step_context(
            uid="worker",
            adjacent_nodes=["orchestrator"]
        )
        
        orchestrator = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="orchestrator"),
            context=orchestrator_context
        )
        
        worker = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="worker"),
            context=worker_context
        )
        
        workflow_id = "workflow_123"
        
        # Phase 1: Orchestrator assigns task
        task_packet = PacketFactory.create_task_packet(
            src_uid="orchestrator",
            dst_uid="worker",
            task_content="Analyze dataset XYZ",
            thread_id=workflow_id
        )
        task_packet.payload["phase"] = "analysis"
        task_packet.payload["priority"] = "high"
        
        orchestrator.send_packet(task_packet)
        
        # Worker receives and acknowledges task
        worker_inbox = worker.inbox_packets()
        assert len(worker_inbox) == 1
        
        task = worker_inbox[0]
        assert task.payload["phase"] == "analysis"
        worker.acknowledge(task.id)
        
        # Phase 2: Worker sends progress update
        progress_packet = PacketFactory.create_task_packet(
            src_uid="worker",
            dst_uid="orchestrator",
            task_content="Analysis 50% complete",
            thread_id=workflow_id
        )
        progress_packet.payload["phase"] = "progress"
        progress_packet.payload["completion_percent"] = 50
        
        worker.send_packet(progress_packet)
        
        # Orchestrator receives progress
        orchestrator_inbox = orchestrator.inbox_packets()
        assert len(orchestrator_inbox) == 1
        
        progress = orchestrator_inbox[0]
        assert progress.payload["phase"] == "progress"
        assert progress.payload["completion_percent"] == 50
        orchestrator.acknowledge(progress.id)
        
        # Phase 3: Worker sends final result
        result_packet = PacketFactory.create_task_packet(
            src_uid="worker",
            dst_uid="orchestrator",
            task_content="Analysis complete: Dataset contains anomalies in sector 7",
            thread_id=workflow_id
        )
        result_packet.payload["phase"] = "result"
        result_packet.payload["anomalies_found"] = True
        result_packet.payload["affected_sector"] = 7
        
        worker.send_packet(result_packet)
        
        # Orchestrator receives final result
        orchestrator_inbox = orchestrator.inbox_packets()
        assert len(orchestrator_inbox) == 1
        
        result = orchestrator_inbox[0]
        assert result.payload["phase"] == "result"
        assert result.payload["anomalies_found"] is True
        assert result.payload["affected_sector"] == 7
        
        result_task = result.extract_task()
        assert "sector 7" in result_task.content
        assert result_task.thread_id == workflow_id
        
        orchestrator.acknowledge(result.id)
        
        # Verify workflow completion
        assert len(orchestrator.inbox_packets()) == 0
        assert len(worker.inbox_packets()) == 0
        
        # Verify all packets in workflow are properly handled
        all_packets = state.get(Channel.INTER_PACKETS, [])
        workflow_packets = [p for p in all_packets if p.payload.get("thread_id") == workflow_id]
        assert len(workflow_packets) == 3  # task, progress, result
        
        # All should be acknowledged by their respective receivers
        for packet in workflow_packets:
            assert packet.is_acknowledged_by(packet.dst.uid)
