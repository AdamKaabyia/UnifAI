"""
Comprehensive tests for IEM middleware pipeline.

Tests middleware execution order, chaining, error handling, and edge cases.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

from mas.core.iem.messenger import DefaultInterMessenger
from mas.core.iem.interfaces import MessengerMiddleware
from mas.core.iem.models import ElementAddress
from mas.core.iem.packets import BaseIEMPacket, TaskPacket
from mas.core.iem.exceptions import IEMValidationException, IEMException
from mas.graph.state.graph_state import Channel
from tests.fixtures.iem_testing_tools import (
    create_test_state_view, PacketFactory, MockMiddleware
)


class LoggingMiddleware(MessengerMiddleware):
    """Middleware that logs all operations."""
    
    def __init__(self):
        self.before_send_calls = []
        self.after_receive_calls = []
    
    def before_send(self, packet: BaseIEMPacket) -> BaseIEMPacket:
        self.before_send_calls.append(packet.id)
        return packet
    
    def after_receive(self, packet: BaseIEMPacket) -> BaseIEMPacket:
        self.after_receive_calls.append(packet.id)
        return packet


class ValidationMiddleware(MessengerMiddleware):
    """Middleware that validates packet contents."""
    
    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self.rejected_packets = []
    
    def before_send(self, packet: BaseIEMPacket) -> BaseIEMPacket:
        if self.strict_mode and not packet.payload:
            self.rejected_packets.append(packet.id)
            raise IEMValidationException("Empty payload not allowed in strict mode")
        return packet
    
    def after_receive(self, packet: BaseIEMPacket) -> BaseIEMPacket:
        if packet.src.uid == "malicious_node":
            self.rejected_packets.append(packet.id)
            raise IEMValidationException("Blocked malicious sender")
        return packet


class TransformationMiddleware(MessengerMiddleware):
    """Middleware that transforms packet data."""
    
    def __init__(self, add_metadata: bool = True):
        self.add_metadata = add_metadata
        self.transformations = []
    
    def before_send(self, packet: BaseIEMPacket) -> BaseIEMPacket:
        if self.add_metadata:
            # Create a new packet with additional metadata
            new_packet = type(packet)(**packet.model_dump())
            new_packet.payload = {
                **packet.payload,
                "middleware_processed": True,
                "processed_at": datetime.utcnow().isoformat()
            }
            self.transformations.append(f"send:{packet.id}")
            return new_packet
        return packet
    
    def after_receive(self, packet: BaseIEMPacket) -> BaseIEMPacket:
        # Add receive timestamp
        new_packet = type(packet)(**packet.model_dump())
        new_packet.payload = {
            **packet.payload,
            "received_at": datetime.utcnow().isoformat()
        }
        self.transformations.append(f"receive:{packet.id}")
        return new_packet


class TestMiddlewarePipeline:
    """Test suite for middleware pipeline functionality."""
    
    def test_single_middleware_execution(self):
        """Test execution of a single middleware."""
        state = create_test_state_view()
        logging_middleware = LoggingMiddleware()
        
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="test_node"),
            middleware=[logging_middleware]
        )
        
        # Test send middleware
        packet = PacketFactory.create_task_packet("sender", "receiver")
        messenger.send_packet(packet)
        
        assert len(logging_middleware.before_send_calls) == 1
        assert logging_middleware.before_send_calls[0] == packet.id
        
        # Test receive middleware
        inbox = messenger.inbox_packets()
        assert len(logging_middleware.after_receive_calls) == 0  # No packets for this node
        
    def test_multiple_middleware_execution_order(self):
        """Test that multiple middleware execute in correct order."""
        state = create_test_state_view()
        
        logging_middleware = LoggingMiddleware()
        validation_middleware = ValidationMiddleware()
        transformation_middleware = TransformationMiddleware()
        
        # Order: logging -> validation -> transformation
        middleware_chain = [logging_middleware, validation_middleware, transformation_middleware]
        
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="test_node"),
            middleware=middleware_chain
        )
        
        packet = PacketFactory.create_task_packet("sender", "test_node")
        messenger.send_packet(packet)
        
        # Verify execution order for send
        assert len(logging_middleware.before_send_calls) == 1
        assert len(transformation_middleware.transformations) == 1
        assert transformation_middleware.transformations[0].startswith("send:")
        
        # Test receive pipeline
        inbox = messenger.inbox_packets()
        assert len(inbox) == 1
        
        # Verify receive pipeline executed
        received_packet = inbox[0]
        assert "received_at" in received_packet.payload
        assert "middleware_processed" in received_packet.payload
        
    def test_middleware_packet_transformation(self):
        """Test that middleware can transform packets."""
        state = create_test_state_view()
        transformation_middleware = TransformationMiddleware()
        
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="test_node"),
            middleware=[transformation_middleware]
        )
        
        original_packet = PacketFactory.create_task_packet("sender", "test_node")
        original_payload_keys = set(original_packet.payload.keys())
        
        messenger.send_packet(original_packet)
        
        # Retrieve and check transformed packet
        inbox = messenger.inbox_packets()
        assert len(inbox) == 1
        
        transformed_packet = inbox[0]
        transformed_payload_keys = set(transformed_packet.payload.keys())
        
        # Should have original keys plus middleware additions
        assert original_payload_keys.issubset(transformed_payload_keys)
        assert "middleware_processed" in transformed_packet.payload
        assert "received_at" in transformed_packet.payload
        
    def test_middleware_validation_rejection(self):
        """Test middleware rejecting packets."""
        state = create_test_state_view()
        validation_middleware = ValidationMiddleware(strict_mode=True)
        
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="test_node"),
            middleware=[validation_middleware]
        )
        
        # Create packet with empty payload (should be rejected)
        empty_packet = TaskPacket(
            src=ElementAddress(uid="sender"),
            dst=ElementAddress(uid="receiver"),
            payload={}
        )
        
        with pytest.raises(IEMValidationException):
            messenger.send_packet(empty_packet)
        
        assert len(validation_middleware.rejected_packets) == 1
        
    def test_middleware_receive_rejection(self):
        """Test middleware rejecting received packets."""
        state = create_test_state_view()
        validation_middleware = ValidationMiddleware()
        
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="test_node"),
            middleware=[validation_middleware]
        )
        
        # Add a packet from malicious sender
        malicious_packet = PacketFactory.create_task_packet("malicious_node", "test_node")
        state[Channel.INTER_PACKETS] = [malicious_packet]
        
        # Should not appear in inbox due to middleware rejection
        inbox = messenger.inbox_packets()
        assert len(inbox) == 0
        assert len(validation_middleware.rejected_packets) == 1
        
    def test_middleware_error_propagation(self):
        """Test error handling in middleware pipeline."""
        state = create_test_state_view()
        
        # Create middleware that throws errors
        error_middleware = Mock(spec=MessengerMiddleware)
        error_middleware.before_send.side_effect = Exception("Middleware error")
        error_middleware.after_receive.return_value = None  # Should not be called
        
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="test_node"),
            middleware=[error_middleware]
        )
        
        packet = PacketFactory.create_task_packet("sender", "receiver")
        
        with pytest.raises(Exception, match="Middleware error"):
            messenger.send_packet(packet)
            
    def test_middleware_chain_interruption(self):
        """Test that middleware chain stops on rejection."""
        state = create_test_state_view()
        
        rejecting_middleware = ValidationMiddleware(strict_mode=True)
        downstream_middleware = LoggingMiddleware()  # Should not be called
        
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="test_node"),
            middleware=[rejecting_middleware, downstream_middleware]
        )
        
        empty_packet = TaskPacket(
            src=ElementAddress(uid="sender"),
            dst=ElementAddress(uid="receiver"),
            payload={}
        )
        
        with pytest.raises(IEMValidationException):
            messenger.send_packet(empty_packet)
        
        # Downstream middleware should not have been called
        assert len(downstream_middleware.before_send_calls) == 0
        
    def test_middleware_performance_impact(self):
        """Test middleware performance characteristics."""
        state = create_test_state_view()
        
        # Create many middleware instances
        middleware_chain = [LoggingMiddleware() for _ in range(10)]
        
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="test_node"),
            middleware=middleware_chain
        )
        
        packet = PacketFactory.create_task_packet("sender", "test_node")
        
        # Measure performance
        import time
        start_time = time.time()
        
        for _ in range(100):
            messenger.send_packet(packet)
            
        duration = time.time() - start_time
        
        # Should complete reasonably quickly (adjust threshold as needed)
        assert duration < 1.0  # 1 second for 100 packets through 10 middleware
        
        # Verify all middleware were called
        for middleware in middleware_chain:
            assert len(middleware.before_send_calls) == 100
            
    def test_middleware_state_isolation(self):
        """Test that middleware don't interfere with each other's state."""
        state = create_test_state_view()
        
        middleware1 = LoggingMiddleware()
        middleware2 = LoggingMiddleware()
        
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="test_node"),
            middleware=[middleware1, middleware2]
        )
        
        packet = PacketFactory.create_task_packet("sender", "receiver")
        messenger.send_packet(packet)
        
        # Both should have recorded the call independently
        assert len(middleware1.before_send_calls) == 1
        assert len(middleware2.before_send_calls) == 1
        assert middleware1.before_send_calls == middleware2.before_send_calls
        
    def test_middleware_complex_transformation_chain(self):
        """Test complex transformation through multiple middleware."""
        state = create_test_state_view()
        
        # Create transformation chain
        metadata_middleware = TransformationMiddleware(add_metadata=True)
        validation_middleware = ValidationMiddleware(strict_mode=False)
        logging_middleware = LoggingMiddleware()
        
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="test_node"),
            middleware=[metadata_middleware, validation_middleware, logging_middleware]
        )
        
        original_packet = PacketFactory.create_task_packet("sender", "test_node")
        messenger.send_packet(original_packet)
        
        # Verify complex pipeline
        inbox = messenger.inbox_packets()
        assert len(inbox) == 1
        
        final_packet = inbox[0]
        
        # Should have transformations from all middleware
        assert "middleware_processed" in final_packet.payload
        assert "received_at" in final_packet.payload
        assert len(logging_middleware.after_receive_calls) == 1
        assert len(metadata_middleware.transformations) == 2  # send + receive
        
    def test_middleware_edge_case_empty_chain(self):
        """Test messenger with no middleware."""
        state = create_test_state_view()
        
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="test_node"),
            middleware=[]  # Empty middleware chain
        )
        
        packet = PacketFactory.create_task_packet("sender", "test_node")
        messenger.send_packet(packet)
        
        inbox = messenger.inbox_packets()
        assert len(inbox) == 1
        
        # Packet should be unchanged
        assert inbox[0].payload == packet.payload
        
    def test_middleware_none_chain(self):
        """Test messenger with None middleware."""
        state = create_test_state_view()
        
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="test_node"),
            middleware=None  # None middleware
        )
        
        packet = PacketFactory.create_task_packet("sender", "test_node")
        messenger.send_packet(packet)
        
        inbox = messenger.inbox_packets()
        assert len(inbox) == 1
        
    def test_middleware_large_packet_handling(self):
        """Test middleware with very large packets."""
        state = create_test_state_view()
        transformation_middleware = TransformationMiddleware()
        
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="test_node"),
            middleware=[transformation_middleware]
        )
        
        # Create large packet
        large_data = "x" * 10000  # 10KB of data
        large_packet = PacketFactory.create_task_packet("sender", "test_node")
        large_packet.payload["large_field"] = large_data
        
        messenger.send_packet(large_packet)
        
        inbox = messenger.inbox_packets()
        assert len(inbox) == 1
        
        # Verify large data preserved through middleware
        assert "large_field" in inbox[0].payload
        assert len(inbox[0].payload["large_field"]) == 10000
        
    def test_middleware_concurrent_access(self):
        """Test middleware with concurrent packet processing."""
        import threading
        import time
        
        state = create_test_state_view()
        logging_middleware = LoggingMiddleware()
        
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="test_node"),
            middleware=[logging_middleware]
        )
        
        def send_packets(count: int):
            for i in range(count):
                packet = PacketFactory.create_task_packet("sender", "receiver", f"packet_{i}")
                messenger.send_packet(packet)
                time.sleep(0.001)  # Small delay
        
        # Start multiple threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=send_packets, args=(10,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify all packets were processed
        assert len(logging_middleware.before_send_calls) == 30  # 3 threads * 10 packets
