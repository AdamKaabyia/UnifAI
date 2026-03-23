"""
Unit tests for IEM acknowledgment system.

Tests acknowledgment tracking, multiple acknowledgments, edge cases,
and acknowledgment-based packet filtering and cleanup.
"""

import pytest
from datetime import datetime, timedelta
from typing import List, Set

from mas.core.iem.packets import TaskPacket
from mas.core.iem.models import ElementAddress
from mas.core.iem.messenger import DefaultInterMessenger
from mas.graph.state.graph_state import Channel
from tests.fixtures.iem_testing_tools import (
    PacketFactory, create_test_state_view, MockIEMNode
)


class TestAcknowledgmentSystem:
    """Test suite for IEM acknowledgment system functionality."""
    
    def test_single_acknowledgment_basic(self):
        """Test basic single acknowledgment functionality."""
        state = create_test_state_view()
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="acknowledger")
        )
        
        # Create and add packet
        packet = PacketFactory.create_task_packet(
            src_uid="sender",
            dst_uid="acknowledger"
        )
        state[Channel.INTER_PACKETS] = [packet]
        
        # Initially not acknowledged
        assert not packet.is_acknowledged_by("acknowledger")
        assert len(packet.ack_by) == 0
        
        # Acknowledge packet
        result = messenger.acknowledge(packet.id)
        
        # Verify acknowledgment
        assert result is True
        assert packet.is_acknowledged_by("acknowledger")
        assert "acknowledger" in packet.ack_by
        assert len(packet.ack_by) == 1
        
    def test_multiple_acknowledgments_same_packet(self):
        """Test multiple nodes acknowledging the same packet."""
        state = create_test_state_view()
        
        # Create multiple messengers
        messengers = {
            f"node_{i}": DefaultInterMessenger(
                state=state,
                identity=ElementAddress(uid=f"node_{i}")
            )
            for i in range(1, 4)  # node_1, node_2, node_3
        }
        
        # Create packet addressed to node_1 but accessible to all for testing
        packet = PacketFactory.create_task_packet(
            src_uid="broadcaster",
            dst_uid="node_1"
        )
        state[Channel.INTER_PACKETS] = [packet]
        
        # Each node acknowledges the packet
        for node_uid, messenger in messengers.items():
            result = messenger.acknowledge(packet.id)
            assert result is True
            assert packet.is_acknowledged_by(node_uid)
            
        # Verify all acknowledgments
        assert len(packet.ack_by) == 3
        for node_uid in messengers.keys():
            assert node_uid in packet.ack_by
            
    def test_acknowledgment_tracking_persistence(self):
        """Test that acknowledgments persist across state operations."""
        state = create_test_state_view()
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="persistent_node")
        )
        
        # Create and acknowledge packet
        packet = PacketFactory.create_task_packet(
            src_uid="sender",
            dst_uid="persistent_node"
        )
        state[Channel.INTER_PACKETS] = [packet]
        
        messenger.acknowledge(packet.id)
        
        # Verify acknowledgment persists
        assert packet.is_acknowledged_by("persistent_node")
        
        # Simulate state reload by getting packets from state
        reloaded_packets = state.get(Channel.INTER_PACKETS, [])
        assert len(reloaded_packets) == 1
        
        reloaded_packet = reloaded_packets[0]
        assert reloaded_packet.is_acknowledged_by("persistent_node")
        
    def test_unacknowledged_packet_handling(self):
        """Test handling of unacknowledged packets in inbox."""
        state = create_test_state_view()
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="receiver")
        )
        
        # Create multiple packets
        packets = [
            PacketFactory.create_task_packet(
                src_uid="sender",
                dst_uid="receiver",
                task_content=f"Message {i}"
            )
            for i in range(5)
        ]
        
        state[Channel.INTER_PACKETS] = packets
        
        # Acknowledge only some packets
        messenger.acknowledge(packets[0].id)
        messenger.acknowledge(packets[2].id)
        messenger.acknowledge(packets[4].id)
        
        # Inbox should only contain unacknowledged packets
        inbox = messenger.inbox_packets()
        assert len(inbox) == 2
        
        unacknowledged_ids = {p.id for p in inbox}
        assert packets[1].id in unacknowledged_ids
        assert packets[3].id in unacknowledged_ids
        
    def test_acknowledgment_edge_cases(self):
        """Test acknowledgment edge cases and error conditions."""
        state = create_test_state_view()
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="edge_tester")
        )
        
        # Test acknowledging non-existent packet
        result = messenger.acknowledge("non_existent_packet_id")
        assert result is False
        
        # Test acknowledging with empty packet ID
        result = messenger.acknowledge("")
        assert result is False
        
        # Test acknowledging with None (should handle gracefully)
        result = messenger.acknowledge(None)
        assert result is False
        
        # Create packet and test valid acknowledgment
        packet = PacketFactory.create_task_packet(
            src_uid="sender",
            dst_uid="edge_tester"
        )
        state[Channel.INTER_PACKETS] = [packet]
        
        result = messenger.acknowledge(packet.id)
        assert result is True
        
        # Test double acknowledgment (should still return True)
        result = messenger.acknowledge(packet.id)
        assert result is True
        assert len(packet.ack_by) == 1  # Should not duplicate
        
    def test_acknowledgment_with_packet_expiration(self):
        """Test acknowledgment behavior with expired packets."""
        state = create_test_state_view()
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="expiry_tester")
        )
        
        # Create expired packet
        expired_packet = PacketFactory.create_expired_packet(
            src_uid="sender",
            dst_uid="expiry_tester"
        )
        
        # Create non-expired packet
        fresh_packet = PacketFactory.create_task_packet(
            src_uid="sender",
            dst_uid="expiry_tester"
        )
        
        state[Channel.INTER_PACKETS] = [expired_packet, fresh_packet]
        
        # Should be able to acknowledge expired packet (acknowledgment is separate from expiration)
        result = messenger.acknowledge(expired_packet.id)
        assert result is True
        
        # Should be able to acknowledge fresh packet
        result = messenger.acknowledge(fresh_packet.id)
        assert result is True
        
        # Inbox should exclude expired packet even if acknowledged
        inbox = messenger.inbox_packets()
        assert len(inbox) == 0  # Fresh packet is acknowledged, expired is excluded
        
    def test_acknowledgment_filtering_by_node(self):
        """Test that acknowledgment filtering works correctly per node."""
        state = create_test_state_view()
        
        # Create multiple messengers
        node1 = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="node_1")
        )
        node2 = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="node_2")
        )
        
        # Create packets for different nodes
        packet1 = PacketFactory.create_task_packet(src_uid="sender", dst_uid="node_1")
        packet2 = PacketFactory.create_task_packet(src_uid="sender", dst_uid="node_2")
        packet3 = PacketFactory.create_task_packet(src_uid="sender", dst_uid="node_1")
        
        state[Channel.INTER_PACKETS] = [packet1, packet2, packet3]
        
        # Node 1 acknowledges its first packet
        node1.acknowledge(packet1.id)
        
        # Node 1 should see only its unacknowledged packet
        node1_inbox = node1.inbox_packets()
        assert len(node1_inbox) == 1
        assert node1_inbox[0].id == packet3.id
        
        # Node 2 should see its packet (unacknowledged)
        node2_inbox = node2.inbox_packets()
        assert len(node2_inbox) == 1
        assert node2_inbox[0].id == packet2.id
        
        # Node 2 acknowledges its packet
        node2.acknowledge(packet2.id)
        
        # Node 2 should now have empty inbox
        node2_inbox = node2.inbox_packets()
        assert len(node2_inbox) == 0
        
        # Node 1 should still see its unacknowledged packet
        node1_inbox = node1.inbox_packets()
        assert len(node1_inbox) == 1
        assert node1_inbox[0].id == packet3.id
        
    def test_acknowledgment_with_broadcast_packets(self):
        """Test acknowledgment behavior with broadcast packets."""
        state = create_test_state_view()
        
        # Create sender
        sender = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="broadcaster")
        )
        
        # Create receiver nodes
        receivers = [
            DefaultInterMessenger(
                state=state,
                identity=ElementAddress(uid=f"receiver_{i}")
            )
            for i in range(3)
        ]
        
        # Broadcast packet to all receivers
        packet = PacketFactory.create_task_packet(
            src_uid="broadcaster",
            dst_uid="placeholder"
        )
        target_uids = [f"receiver_{i}" for i in range(3)]
        
        packet_ids = sender.multicast_packet(packet, target_uids)
        assert len(packet_ids) == 3
        
        # Each receiver should see their copy
        for i, receiver in enumerate(receivers):
            inbox = receiver.inbox_packets()
            assert len(inbox) == 1
            
        # Acknowledge from first two receivers only
        for i in range(2):
            inbox = receivers[i].inbox_packets()
            receivers[i].acknowledge(inbox[0].id)
            
        # Third receiver should still see unacknowledged packet
        inbox = receivers[2].inbox_packets()
        assert len(inbox) == 1
        
        # First two receivers should have empty inboxes
        for i in range(2):
            inbox = receivers[i].inbox_packets()
            assert len(inbox) == 0
            
    def test_acknowledgment_state_consistency(self):
        """Test acknowledgment state consistency across operations."""
        state = create_test_state_view()
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="consistency_tester")
        )
        
        # Create packets
        packets = [
            PacketFactory.create_task_packet(
                src_uid="sender",
                dst_uid="consistency_tester",
                task_content=f"Packet {i}"
            )
            for i in range(10)
        ]
        
        state[Channel.INTER_PACKETS] = packets
        
        # Acknowledge packets in random order
        acknowledge_order = [2, 7, 1, 9, 4]
        for i in acknowledge_order:
            result = messenger.acknowledge(packets[i].id)
            assert result is True
            
        # Verify acknowledged packets are not in inbox
        inbox = messenger.inbox_packets()
        inbox_ids = {p.id for p in inbox}
        
        for i in acknowledge_order:
            assert packets[i].id not in inbox_ids
            
        # Verify unacknowledged packets are in inbox
        unacknowledged_indices = [0, 3, 5, 6, 8]
        for i in unacknowledged_indices:
            assert packets[i].id in inbox_ids
            
        assert len(inbox) == len(unacknowledged_indices)
        
    def test_acknowledgment_performance_with_many_packets(self):
        """Test acknowledgment performance with large number of packets."""
        state = create_test_state_view()
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="performance_tester")
        )
        
        # Create many packets
        packet_count = 1000
        packets = [
            PacketFactory.create_task_packet(
                src_uid="sender",
                dst_uid="performance_tester",
                task_content=f"Packet {i}"
            )
            for i in range(packet_count)
        ]
        
        state[Channel.INTER_PACKETS] = packets
        
        # Acknowledge all packets
        acknowledged_count = 0
        for packet in packets:
            result = messenger.acknowledge(packet.id)
            if result:
                acknowledged_count += 1
                
        assert acknowledged_count == packet_count
        
        # Verify inbox is empty
        inbox = messenger.inbox_packets()
        assert len(inbox) == 0
        
    def test_acknowledgment_with_concurrent_operations(self):
        """Test acknowledgment behavior with concurrent state modifications."""
        state = create_test_state_view()
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="concurrent_tester")
        )
        
        # Create initial packets
        packets = [
            PacketFactory.create_task_packet(
                src_uid="sender",
                dst_uid="concurrent_tester",
                task_content=f"Initial {i}"
            )
            for i in range(5)
        ]
        
        state[Channel.INTER_PACKETS] = packets
        
        # Acknowledge some packets
        messenger.acknowledge(packets[0].id)
        messenger.acknowledge(packets[2].id)
        
        # Add more packets while some are acknowledged
        new_packets = [
            PacketFactory.create_task_packet(
                src_uid="sender",
                dst_uid="concurrent_tester",
                task_content=f"New {i}"
            )
            for i in range(3)
        ]
        
        current_packets = state.get(Channel.INTER_PACKETS, [])
        current_packets.extend(new_packets)
        state[Channel.INTER_PACKETS] = current_packets
        
        # Acknowledge new packets
        for packet in new_packets:
            messenger.acknowledge(packet.id)
            
        # Verify correct acknowledgment state
        inbox = messenger.inbox_packets()
        # The test logic is correct: 5 initial packets, acknowledge 2, expect 3 remaining
        # packets[0] and packets[2] are acknowledged → packets[1], packets[3], packets[4] remain
        # All new_packets are also acknowledged → they shouldn't appear in inbox
        expected_remaining = 3
        assert len(inbox) == expected_remaining, f"Expected {expected_remaining} unacknowledged packets, got {len(inbox)}"
        
        inbox_contents = [p.extract_task().content for p in inbox]
        assert "Initial 1" in inbox_contents  # packets[1] 
        assert "Initial 3" in inbox_contents  # packets[3]
        assert "Initial 4" in inbox_contents  # packets[4]
        
    def test_acknowledgment_cleanup_integration(self):
        """Test acknowledgment integration with packet cleanup/purging."""
        state = create_test_state_view()
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="cleanup_tester")
        )
        
        # Create packets with different acknowledgment states
        acknowledged_packets = [
            PacketFactory.create_task_packet(
                src_uid="sender",
                dst_uid="cleanup_tester",
                task_content=f"Acked {i}"
            )
            for i in range(3)
        ]
        
        unacknowledged_packets = [
            PacketFactory.create_task_packet(
                src_uid="sender",
                dst_uid="cleanup_tester",
                task_content=f"Unacked {i}"
            )
            for i in range(2)
        ]
        
        all_packets = acknowledged_packets + unacknowledged_packets
        state[Channel.INTER_PACKETS] = all_packets
        
        # Acknowledge specific packets
        for packet in acknowledged_packets:
            messenger.acknowledge(packet.id)
            
        # Verify acknowledgment state
        for packet in acknowledged_packets:
            assert packet.is_acknowledged_by("cleanup_tester")
            
        for packet in unacknowledged_packets:
            assert not packet.is_acknowledged_by("cleanup_tester")
            
        # Purge acknowledged packets
        purged_count = messenger.purge(acked_only=True)
        assert purged_count == 3
        
        # Verify only unacknowledged packets remain
        remaining_packets = state.get(Channel.INTER_PACKETS, [])
        assert len(remaining_packets) == 2
        
        for packet in remaining_packets:
            assert not packet.is_acknowledged_by("cleanup_tester")
            
        # Verify inbox contains remaining packets
        inbox = messenger.inbox_packets()
        assert len(inbox) == 2
