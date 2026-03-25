"""
Unit tests for specific IEM packet types.

Tests TaskPacket, SystemPacket, and DebugPacket functionality.
Covers packet creation, payload handling, and type-specific features.
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any

from mas.core.iem.packets import TaskPacket, SystemPacket, DebugPacket
from mas.core.iem.models import ElementAddress, PacketType
from mas.elements.nodes.common.workload import Task
from tests.fixtures.iem_testing_tools import PacketFactory


class TestTaskPacket:
    """Test suite for TaskPacket functionality."""
    
    def test_task_packet_creation(self):
        """Test basic TaskPacket creation."""
        src = ElementAddress(uid="agent_1")
        dst = ElementAddress(uid="agent_2")
        task = Task.create(content="Test task", created_by="agent_1")
        
        packet = TaskPacket.create(src=src, dst=dst, task=task)
        
        assert packet.type == PacketType.TASK
        assert packet.src == src
        assert packet.dst == dst
        assert isinstance(packet.payload, dict)
        assert "content" in packet.payload
        assert packet.payload["content"] == "Test task"
        
    def test_task_extraction_from_payload(self):
        """Test extracting Task object from packet payload."""
        task = Task.create(
            content="Complex task",
            data={"param1": "value1", "param2": 42},
            should_respond=True,
            created_by="test_agent"
        )
        
        packet = PacketFactory.create_task_packet(
            src_uid="src",
            dst_uid="dst",
            task_content=task.content
        )
        
        # Replace payload with our custom task
        packet.payload = task.model_dump()
        
        extracted_task = packet.extract_task()
        
        assert isinstance(extracted_task, Task)
        assert extracted_task.content == "Complex task"
        assert extracted_task.created_by == "test_agent"
        
    def test_invalid_task_payload_handling(self):
        """Test handling of invalid task payloads."""
        packet = TaskPacket(
            src=ElementAddress(uid="src"),
            dst=ElementAddress(uid="dst"),
            payload={"invalid": "payload"}  # Missing required Task fields
        )
        
        with pytest.raises(Exception):
            packet.extract_task()
            
    def test_task_packet_factory_method(self):
        """Test TaskPacket.create() factory method."""
        task = Task.create(
            content="Factory test task",
            thread_id="test_thread_123",
            should_respond=False
        )
        
        packet = TaskPacket.create(
            src=ElementAddress(uid="factory_src"),
            dst=ElementAddress(uid="factory_dst"),
            task=task
        )
        
        assert packet.type == PacketType.TASK
        assert packet.src.uid == "factory_src"
        assert packet.dst.uid == "factory_dst"
        
        # Verify task can be extracted
        extracted_task = packet.extract_task()
        assert extracted_task.content == "Factory test task"
        assert extracted_task.thread_id == "test_thread_123"
        
    def test_task_packet_with_complex_task_data(self):
        """Test TaskPacket with complex task data structures."""
        complex_data = {
            "nested_dict": {"key1": "value1", "key2": {"nested": True}},
            "list_data": [1, 2, 3, "string", {"item": "value"}],
            "metadata": {
                "created_at": datetime.utcnow().isoformat(),
                "priority": "high",
                "tags": ["urgent", "customer-facing"]
            }
        }
        
        task = Task.create(
            content="Complex data task",
            data=complex_data
        )
        
        packet = TaskPacket.create(
            src=ElementAddress(uid="src"),
            dst=ElementAddress(uid="dst"),
            task=task
        )
        
        # Verify complex data survives serialization/deserialization
        extracted_task = packet.extract_task()
        assert extracted_task.data == complex_data
        
    def test_task_packet_with_large_payload(self):
        """Test TaskPacket with large payload data."""
        large_data = "x" * 10000  # 10KB of data
        task = Task.create(
            content="Large task",
            data={"large_field": large_data}
        )
        
        packet = TaskPacket.create(
            src=ElementAddress(uid="src"),
            dst=ElementAddress(uid="dst"),
            task=task
        )
        
        extracted_task = packet.extract_task()
        assert extracted_task.data["large_field"] == large_data
        
    def test_task_packet_serialization_roundtrip(self):
        """Test complete serialization roundtrip for TaskPacket."""
        original_task = Task.create(
            content="Serialization test",
            data={"key": "value"},
            should_respond=True,
            thread_id="thread_123"
        )
        
        original_packet = TaskPacket.create(
            src=ElementAddress(uid="original_src"),
            dst=ElementAddress(uid="original_dst"),
            task=original_task
        )
        
        # Serialize to dict
        packet_dict = original_packet.model_dump()
        
        # Deserialize back
        reconstructed_packet = TaskPacket.model_validate(packet_dict)
        
        # Verify packet integrity
        assert reconstructed_packet.id == original_packet.id
        assert reconstructed_packet.src == original_packet.src
        assert reconstructed_packet.dst == original_packet.dst
        
        # Verify task integrity
        reconstructed_task = reconstructed_packet.extract_task()
        assert reconstructed_task.content == original_task.content
        assert reconstructed_task.thread_id == original_task.thread_id


class TestSystemPacket:
    """Test suite for SystemPacket functionality."""
    
    def test_system_packet_creation(self):
        """Test basic SystemPacket creation."""
        packet = SystemPacket(
            src=ElementAddress(uid="system"),
            dst=ElementAddress(uid="node_1"),
            system_event="node_health_check",
            data={"status": "healthy", "load": 0.75}
        )
        
        assert packet.type == PacketType.SYSTEM
        assert packet.system_event == "node_health_check"
        assert packet.data["status"] == "healthy"
        assert packet.data["load"] == 0.75
        
    def test_system_event_handling(self):
        """Test various system event types."""
        events = [
            ("node_startup", {"node_id": "worker_1", "capabilities": ["llm", "retrieval"]}),
            ("node_shutdown", {"node_id": "worker_2", "reason": "maintenance"}),
            ("network_partition", {"affected_nodes": ["node_1", "node_2"]}),
            ("resource_alert", {"resource": "memory", "usage": 0.95, "threshold": 0.9}),
            ("configuration_update", {"config_key": "max_connections", "old_value": 10, "new_value": 20})
        ]
        
        for event_type, event_data in events:
            packet = SystemPacket(
                src=ElementAddress(uid="system_monitor"),
                dst=ElementAddress(uid="target_node"),
                system_event=event_type,
                data=event_data
            )
            
            assert packet.system_event == event_type
            assert packet.data == event_data
            
    def test_system_packet_with_empty_data(self):
        """Test SystemPacket with empty or minimal data."""
        packet = SystemPacket(
            src=ElementAddress(uid="system"),
            dst=ElementAddress(uid="node"),
            system_event="ping"
        )
        
        assert packet.system_event == "ping"
        assert packet.data == {}
        
    def test_system_packet_serialization(self):
        """Test SystemPacket serialization and deserialization."""
        original_packet = SystemPacket(
            src=ElementAddress(uid="monitor"),
            dst=ElementAddress(uid="worker"),
            system_event="performance_report",
            data={
                "cpu_usage": 0.65,
                "memory_usage": 0.80,
                "active_tasks": 5,
                "completed_tasks": 100,
                "error_count": 2
            }
        )
        
        # Serialize
        packet_dict = original_packet.model_dump()
        
        # Deserialize
        reconstructed_packet = SystemPacket.model_validate(packet_dict)
        
        assert reconstructed_packet.system_event == original_packet.system_event
        assert reconstructed_packet.data == original_packet.data
        
    def test_system_packet_with_complex_nested_data(self):
        """Test SystemPacket with complex nested data structures."""
        complex_data = {
            "metrics": {
                "performance": {
                    "avg_response_time": 150.5,
                    "throughput": 1200,
                    "error_rates": {"timeout": 0.02, "validation": 0.001}
                },
                "resources": {
                    "cpu": {"cores": 8, "usage_per_core": [0.1, 0.3, 0.6, 0.2, 0.8, 0.1, 0.4, 0.5]},
                    "memory": {"total_gb": 32, "used_gb": 12.5, "swap_gb": 0.1}
                }
            },
            "alerts": [
                {"level": "warning", "message": "High CPU usage on core 4"},
                {"level": "info", "message": "Cache hit rate improved"}
            ]
        }
        
        packet = SystemPacket(
            src=ElementAddress(uid="metrics_collector"),
            dst=ElementAddress(uid="dashboard"),
            system_event="metrics_update",
            data=complex_data
        )
        
        # Verify complex data is preserved
        assert packet.data == complex_data
        assert packet.data["metrics"]["performance"]["avg_response_time"] == 150.5
        assert len(packet.data["alerts"]) == 2


class TestDebugPacket:
    """Test suite for DebugPacket functionality."""
    
    def test_debug_packet_creation(self):
        """Test basic DebugPacket creation."""
        debug_info = {
            "log_level": "DEBUG",
            "component": "task_processor", 
            "message": "Processing task batch",
            "context": {"batch_size": 10, "thread_id": "worker_1"}
        }
        
        packet = DebugPacket(
            src=ElementAddress(uid="worker_node"),
            dst=ElementAddress(uid="debug_collector"),
            debug_info=debug_info
        )
        
        assert packet.type == PacketType.DEBUG
        assert packet.debug_info == debug_info
        
    def test_debug_info_structure(self):
        """Test various debug info structures."""
        debug_scenarios = [
            # Performance debugging
            {
                "category": "performance",
                "operation": "packet_send",
                "duration_ms": 45.2,
                "metadata": {"packet_size": 1024, "destination": "remote_node"}
            },
            # Error debugging
            {
                "category": "error",
                "error_type": "ValidationError",
                "error_message": "Invalid packet format",
                "stack_trace": ["line1", "line2", "line3"],
                "context": {"packet_id": "abc123", "src_node": "node_1"}
            },
            # State debugging
            {
                "category": "state",
                "component": "messenger",
                "state_snapshot": {
                    "pending_packets": 5,
                    "acknowledged_packets": 100,
                    "active_connections": 3
                }
            },
            # Flow debugging
            {
                "category": "flow",
                "workflow_id": "workflow_123",
                "step": "task_distribution",
                "participants": ["node_1", "node_2", "node_3"],
                "current_state": "distributing"
            }
        ]
        
        for debug_info in debug_scenarios:
            packet = DebugPacket(
                src=ElementAddress(uid="debug_source"),
                dst=ElementAddress(uid="debug_sink"),
                debug_info=debug_info
            )
            
            assert packet.debug_info == debug_info
            assert packet.debug_info["category"] == debug_info["category"]
            
    def test_debug_packet_with_empty_info(self):
        """Test DebugPacket with empty debug info."""
        packet = DebugPacket(
            src=ElementAddress(uid="src"),
            dst=ElementAddress(uid="dst")
        )
        
        assert packet.debug_info == {}
        
    def test_debug_packet_with_large_debug_data(self):
        """Test DebugPacket with large debug data."""
        large_debug_info = {
            "component": "stress_test",
            "large_data": "x" * 50000,  # 50KB of debug data
            "structured_data": {f"key_{i}": f"value_{i}" for i in range(1000)},
            "list_data": [{"item": i, "data": "x" * 100} for i in range(100)]
        }
        
        packet = DebugPacket(
            src=ElementAddress(uid="stress_tester"),
            dst=ElementAddress(uid="debug_collector"),
            debug_info=large_debug_info
        )
        
        assert packet.debug_info == large_debug_info
        assert len(packet.debug_info["large_data"]) == 50000
        assert len(packet.debug_info["structured_data"]) == 1000
        
    def test_debug_packet_serialization(self):
        """Test DebugPacket serialization with various debug info types."""
        debug_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "log_level": "TRACE",
            "thread_id": "debug_thread_123",
            "function": "process_debug_packet",
            "variables": {
                "counter": 42,
                "flag": True,
                "nullable": None,
                "list": [1, 2, 3],
                "nested": {"inner": "value"}
            }
        }
        
        original_packet = DebugPacket(
            src=ElementAddress(uid="debugger"),
            dst=ElementAddress(uid="logger"),
            debug_info=debug_info
        )
        
        # Serialize
        packet_dict = original_packet.model_dump()
        
        # Deserialize
        reconstructed_packet = DebugPacket.model_validate(packet_dict)
        
        assert reconstructed_packet.debug_info == original_packet.debug_info
        assert reconstructed_packet.debug_info["variables"]["counter"] == 42
        assert reconstructed_packet.debug_info["variables"]["flag"] is True
        assert reconstructed_packet.debug_info["variables"]["nullable"] is None


class TestPacketTypeInteroperability:
    """Test interoperability between different packet types."""
    
    def test_packet_type_identification(self):
        """Test that packet types can be correctly identified."""
        task_packet = PacketFactory.create_task_packet()
        system_packet = PacketFactory.create_system_packet()
        debug_packet = PacketFactory.create_debug_packet()
        
        assert task_packet.type == PacketType.TASK
        assert system_packet.type == PacketType.SYSTEM
        assert debug_packet.type == PacketType.DEBUG
        
        # Verify they're different
        packet_types = {task_packet.type, system_packet.type, debug_packet.type}
        assert len(packet_types) == 3
        
    def test_mixed_packet_handling(self):
        """Test handling of mixed packet types in a collection."""
        packets = [
            PacketFactory.create_task_packet(src_uid="node_1", dst_uid="node_2"),
            PacketFactory.create_system_packet(src_uid="system", dst_uid="node_2"),
            PacketFactory.create_debug_packet(src_uid="node_2", dst_uid="debugger"),
            PacketFactory.create_task_packet(src_uid="node_3", dst_uid="node_1"),
        ]
        
        # Filter by type
        task_packets = [p for p in packets if p.type == PacketType.TASK]
        system_packets = [p for p in packets if p.type == PacketType.SYSTEM]
        debug_packets = [p for p in packets if p.type == PacketType.DEBUG]
        
        assert len(task_packets) == 2
        assert len(system_packets) == 1
        assert len(debug_packets) == 1
        
    def test_packet_polymorphism(self):
        """Test polymorphic handling of different packet types."""
        packets = [
            PacketFactory.create_task_packet(),
            PacketFactory.create_system_packet(), 
            PacketFactory.create_debug_packet()
        ]
        
        # All packets should have common BaseIEMPacket interface
        for packet in packets:
            assert hasattr(packet, 'id')
            assert hasattr(packet, 'protocol')
            assert hasattr(packet, 'type')
            assert hasattr(packet, 'src')
            assert hasattr(packet, 'dst')
            assert hasattr(packet, 'ts')
            assert hasattr(packet, 'acknowledge')
            assert hasattr(packet, 'is_acknowledged_by')
            assert hasattr(packet, 'is_expired')
            
        # Each should acknowledge properly
        for i, packet in enumerate(packets):
            node_id = f"node_{i}"
            packet.acknowledge(node_id)
            assert packet.is_acknowledged_by(node_id)
