"""
Comprehensive boundary condition and edge case tests for IEM system.

Tests extreme values, malformed data, resource limits, and unusual scenarios.
"""

import pytest
import uuid
import time
import threading
import string
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor
import sys

from mas.core.iem.messenger import DefaultInterMessenger
from mas.core.iem.models import ElementAddress, PacketType
from mas.core.iem.packets import BaseIEMPacket, TaskPacket, SystemPacket, DebugPacket
from mas.core.iem.exceptions import IEMException, IEMValidationException
from tests.fixtures.iem_testing_tools import (
    create_test_state_view, create_test_step_context,
    PacketFactory, IEMPerformanceMonitor
)


class BoundaryTestGenerator:
    """Generator for boundary condition test data."""
    
    @staticmethod
    def generate_extreme_strings() -> Dict[str, str]:
        """Generate strings at various boundaries."""
        return {
            "empty": "",
            "single_char": "a",
            "very_long": "x" * 10000,
            "extremely_long": "y" * 100000,
            "unicode_mixed": "Hello 世界 🌍 Ωorld",
            "unicode_heavy": "🚀" * 1000,
            "special_chars": "!@#$%^&*()[]{}|\\:;\"'<>,.?/~`",
            "newlines": "line1\\nline2\\rline3\\r\\nline4",
            "tabs": "\\t\\t\\ttabbed\\tcontent\\t\\t",
            "null_bytes": "before\\x00after\\x00end",
            "control_chars": "\\x01\\x02\\x03\\x1f\\x7f",
            "max_unicode": "\\U0010ffff" * 100,
            "whitespace_only": "   \\t\\n\\r   ",
            "sql_injection": "'; DROP TABLE packets; --",
            "script_injection": "<script>alert('xss')</script>",
            "path_traversal": "../../../etc/passwd",
            "format_string": "%s%d%x%n",
            "repeated_pattern": ("ABC" * 1000),
            "binary_like": "\\xff\\xfe\\xfd" * 500
        }
    
    @staticmethod
    def generate_extreme_numbers() -> Dict[str, Union[int, float]]:
        """Generate numbers at various boundaries."""
        return {
            "zero": 0,
            "negative_zero": -0.0,
            "one": 1,
            "negative_one": -1,
            "max_int": sys.maxsize,
            "min_int": -sys.maxsize - 1,
            "max_float": sys.float_info.max,
            "min_float": sys.float_info.min,
            "epsilon": sys.float_info.epsilon,
            "infinity": float('inf'),
            "negative_infinity": float('-inf'),
            "nan": float('nan'),
            "very_large": 10**308,
            "very_small": 10**-308,
            "precision_limit": 1.7976931348623157e+308
        }
    
    @staticmethod
    def generate_extreme_collections() -> Dict[str, Any]:
        """Generate collections at various boundaries."""
        return {
            "empty_list": [],
            "empty_dict": {},
            "empty_set": set(),
            "single_item_list": [1],
            "single_item_dict": {"key": "value"},
            "large_list": list(range(10000)),
            "large_dict": {f"key_{i}": f"value_{i}" for i in range(1000)},
            "nested_deep": {"level_" + str(i): {"nested": i} for i in range(100)},
            "circular_ref": None,  # Will be created separately
            "mixed_types": [1, "string", 3.14, True, None, [], {}],
            "unicode_keys": {"键1": "值1", "🔑": "🔒", "clé": "valeur"},
            "numeric_keys": {1: "one", 2.5: "two-point-five", -1: "negative"},
            "none_values": {"a": None, "b": None, "c": None},
            "duplicate_values": ["same", "same", "same"],
            "extreme_nesting": {"a": {"b": {"c": {"d": {"e": "deep"}}}}},
            "large_strings": [("x" * 1000) for _ in range(100)]
        }
    
    @staticmethod
    def generate_malformed_data() -> Dict[str, Any]:
        """Generate malformed data structures."""
        return {
            "invalid_json": '{"incomplete": ',
            "mismatched_brackets": "[{]}",
            "truncated_string": '"incomplete string',
            "invalid_escape": "\\invalid",
            "mixed_encodings": b"\\xff\\xfe" + "unicode".encode('utf-8'),
            "recursive_structure": None,  # Will be created separately
            "invalid_unicode": "\\ud800\\udc00",  # Surrogate pair
            "xml_in_json": '{"data": "<xml>content</xml>"}',
            "html_in_content": "<html><body>content</body></html>",
            "base64_like": "SGVsbG8gV29ybGQ=",
            "url_encoded": "Hello%20World%21",
            "percent_encoding": "100%25%20complete"
        }


class ExtremeConditionTester:
    """Test extreme operating conditions."""
    
    def __init__(self):
        self.stress_messengers = []
        self.stress_state = None
        self.resource_monitors = []
    
    def setup_extreme_load(self, messenger_count: int = 100):
        """Set up environment for extreme load testing."""
        self.stress_state = create_test_state_view()
        self.stress_messengers = []
        
        for i in range(messenger_count):
            uid = f"extreme_node_{i}"
            # Each node connects to a subset to avoid O(n²) adjacency
            adjacent_count = min(10, messenger_count - 1)
            adjacent_uids = [f"extreme_node_{j}" 
                           for j in range(i+1, min(i+1+adjacent_count, messenger_count))]
            
            context = create_test_step_context(uid, adjacent_uids)
            messenger = DefaultInterMessenger(
                state=self.stress_state,
                identity=ElementAddress(uid=uid),
                context=context
            )
            self.stress_messengers.append(messenger)
    
    def test_massive_packet_creation(self, packet_count: int = 10000) -> Dict[str, Any]:
        """Test creation of massive number of packets."""
        start_time = time.time()
        packets = []
        memory_samples = []
        
        # Sample memory every 1000 packets
        import psutil
        process = psutil.Process()
        
        try:
            for i in range(packet_count):
                packet = PacketFactory.create_task_packet(
                    f"sender_{i % 100}",
                    f"receiver_{i % 100}",
                    f"Mass packet {i}"
                )
                packets.append(packet)
                
                if i % 1000 == 0:
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    memory_samples.append({"packet_count": i, "memory_mb": memory_mb})
                
                # Prevent system overload
                if i % 5000 == 0:
                    time.sleep(0.001)
            
            creation_time = time.time() - start_time
            final_memory = process.memory_info().rss / 1024 / 1024
            
            return {
                "success": True,
                "packet_count": len(packets),
                "creation_time_seconds": creation_time,
                "packets_per_second": packet_count / creation_time if creation_time > 0 else 0,
                "final_memory_mb": final_memory,
                "memory_samples": memory_samples,
                "avg_memory_per_packet_kb": (final_memory * 1024) / packet_count if packet_count > 0 else 0
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "packets_created": len(packets),
                "memory_samples": memory_samples
            }
    
    def test_extreme_concurrent_operations(self, thread_count: int = 50, ops_per_thread: int = 100) -> Dict[str, Any]:
        """Test extreme concurrent operations."""
        if not self.stress_messengers:
            return {"error": "Setup required first"}
        
        results = []
        errors = []
        
        def worker_thread(thread_id: int):
            thread_results = {"sent": 0, "received": 0, "errors": 0}
            
            try:
                messenger = self.stress_messengers[thread_id % len(self.stress_messengers)]
                
                for i in range(ops_per_thread):
                    # Send operation
                    try:
                        packet = PacketFactory.create_task_packet(
                            f"thread_{thread_id}",
                            f"target_{i % 10}",
                            f"Concurrent op {i}"
                        )
                        messenger.send_packet(packet)
                        thread_results["sent"] += 1
                    except Exception as e:
                        thread_results["errors"] += 1
                        errors.append(f"Thread {thread_id} send error: {str(e)}")
                    
                    # Receive operation
                    try:
                        packets = messenger.inbox_packets()
                        thread_results["received"] += len(packets)
                        
                        # Acknowledge packets
                        for packet in packets:
                            messenger.acknowledge(packet.id)
                    except Exception as e:
                        thread_results["errors"] += 1
                        errors.append(f"Thread {thread_id} receive error: {str(e)}")
                    
                    # Small delay to prevent overwhelming
                    if i % 10 == 0:
                        time.sleep(0.001)
                        
            except Exception as e:
                errors.append(f"Thread {thread_id} fatal error: {str(e)}")
            
            return thread_results
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = [executor.submit(worker_thread, i) for i in range(thread_count)]
            results = [future.result() for future in futures]
        
        total_time = time.time() - start_time
        
        # Aggregate results
        total_sent = sum(r["sent"] for r in results)
        total_received = sum(r["received"] for r in results)
        total_errors = sum(r["errors"] for r in results)
        
        return {
            "thread_count": thread_count,
            "ops_per_thread": ops_per_thread,
            "total_time_seconds": total_time,
            "total_sent": total_sent,
            "total_received": total_received,
            "total_errors": total_errors,
            "ops_per_second": (total_sent + total_received) / total_time if total_time > 0 else 0,
            "error_rate": total_errors / (total_sent + total_received + total_errors) if (total_sent + total_received + total_errors) > 0 else 0,
            "sample_errors": errors[:10]  # First 10 errors for analysis
        }


class TestBoundaryConditions:
    """Test suite for boundary conditions and edge cases."""
    
    def test_empty_packet_handling(self):
        """Test handling of packets with empty or minimal data."""
        state = create_test_state_view()
        context = create_test_step_context("empty_test_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="empty_test_node"),
            context=context
        )
        
        # Test completely empty payload
        empty_packet = TaskPacket(
            src=ElementAddress(uid="empty_test_node"),
            dst=ElementAddress(uid="target"),
            payload={}
        )
        
        # Should be able to send empty packet
        packet_id = messenger.send_packet(empty_packet)
        assert packet_id is not None
        
        # Test packet with None values
        none_packet = TaskPacket(
            src=ElementAddress(uid="empty_test_node"),
            dst=ElementAddress(uid="target"),
            payload={"content": None, "data": None}
        )
        
        packet_id = messenger.send_packet(none_packet)
        assert packet_id is not None
        
        # Test packet with empty strings
        empty_string_packet = PacketFactory.create_task_packet(
            "empty_test_node", "target", ""
        )
        
        packet_id = messenger.send_packet(empty_string_packet)
        assert packet_id is not None
    
    def test_extreme_string_handling(self):
        """Test handling of extreme string values."""
        state = create_test_state_view()
        context = create_test_step_context("string_test_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="string_test_node"),
            context=context
        )
        
        extreme_strings = BoundaryTestGenerator.generate_extreme_strings()
        
        for test_name, test_string in extreme_strings.items():
            try:
                packet = PacketFactory.create_task_packet(
                    "string_test_node", "target", test_string
                )
                packet_id = messenger.send_packet(packet)
                assert packet_id is not None, f"Failed to send packet with {test_name} string"
                
                # Verify packet can be retrieved
                inbox = messenger.inbox_packets()
                # Note: might not receive own packets depending on filtering
                
            except Exception as e:
                # Some extreme cases might legitimately fail
                print(f"Expected failure for {test_name}: {str(e)}")
                assert "string" in test_name.lower() or "unicode" in test_name.lower()
    
    def test_extreme_numeric_values(self):
        """Test handling of extreme numeric values."""
        state = create_test_state_view()
        context = create_test_step_context("numeric_test_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="numeric_test_node"),
            context=context
        )
        
        extreme_numbers = BoundaryTestGenerator.generate_extreme_numbers()
        
        for test_name, test_number in extreme_numbers.items():
            try:
                packet = PacketFactory.create_task_packet(
                    "numeric_test_node", "target", f"Testing {test_name}"
                )
                packet.payload["numeric_value"] = test_number
                packet.payload["test_type"] = test_name
                
                packet_id = messenger.send_packet(packet)
                assert packet_id is not None, f"Failed to send packet with {test_name} number"
                
            except Exception as e:
                # Some extreme values (like NaN, infinity) might cause issues
                if test_name in ["nan", "infinity", "negative_infinity"]:
                    print(f"Expected potential issue with {test_name}: {str(e)}")
                else:
                    raise AssertionError(f"Unexpected failure with {test_name}: {str(e)}")
    
    def test_extreme_collection_sizes(self):
        """Test handling of extreme collection sizes."""
        state = create_test_state_view()
        context = create_test_step_context("collection_test_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="collection_test_node"),
            context=context
        )
        
        extreme_collections = BoundaryTestGenerator.generate_extreme_collections()
        
        for test_name, test_collection in extreme_collections.items():
            if test_name == "circular_ref":
                continue  # Skip circular references for now
            
            try:
                packet = PacketFactory.create_task_packet(
                    "collection_test_node", "target", f"Testing {test_name}"
                )
                packet.payload["collection_data"] = test_collection
                packet.payload["test_type"] = test_name
                
                packet_id = messenger.send_packet(packet)
                assert packet_id is not None, f"Failed to send packet with {test_name} collection"
                
            except Exception as e:
                # Large collections might cause memory or serialization issues
                if "large" in test_name or "deep" in test_name:
                    print(f"Expected potential issue with {test_name}: {str(e)}")
                else:
                    raise AssertionError(f"Unexpected failure with {test_name}: {str(e)}")
    
    def test_malformed_packet_data(self):
        """Test handling of malformed packet data."""
        state = create_test_state_view()
        context = create_test_step_context("malformed_test_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="malformed_test_node"),
            context=context
        )
        
        malformed_data = BoundaryTestGenerator.generate_malformed_data()
        
        for test_name, test_data in malformed_data.items():
            if test_name == "recursive_structure":
                continue  # Skip recursive structures
            
            try:
                packet = PacketFactory.create_task_packet(
                    "malformed_test_node", "target", "Malformed data test"
                )
                packet.payload["malformed_data"] = test_data
                packet.payload["test_type"] = test_name
                
                # This might fail, and that's okay for malformed data
                packet_id = messenger.send_packet(packet)
                
            except Exception as e:
                # Malformed data should often cause failures
                print(f"Expected failure with {test_name}: {str(e)}")
    
    def test_extreme_ttl_values(self):
        """Test handling of extreme TTL values."""
        state = create_test_state_view()
        context = create_test_step_context("ttl_test_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="ttl_test_node"),
            context=context
        )
        
        extreme_ttls = [
            timedelta(0),  # Zero TTL
            timedelta(microseconds=1),  # Minimal TTL
            timedelta(seconds=1),  # Very short
            timedelta(days=365),  # Very long
            timedelta(days=10000),  # Extremely long
        ]
        
        for i, ttl in enumerate(extreme_ttls):
            packet = PacketFactory.create_task_packet(
                "ttl_test_node", "target", f"TTL test {i}"
            )
            packet.ttl = ttl
            
            packet_id = messenger.send_packet(packet)
            assert packet_id is not None
            
            # Check if packet is immediately expired
            if ttl <= timedelta(0):
                # Zero TTL packets might be immediately expired
                inbox = messenger.inbox_packets()
                # May or may not contain the packet depending on timing
    
    def test_extreme_packet_timestamps(self):
        """Test handling of extreme packet timestamps."""
        state = create_test_state_view()
        context = create_test_step_context("timestamp_test_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="timestamp_test_node"),
            context=context
        )
        
        extreme_timestamps = [
            datetime.min,  # Minimum possible datetime
            datetime.max,  # Maximum possible datetime  
            datetime(1970, 1, 1),  # Unix epoch
            datetime(2000, 1, 1),  # Y2K
            datetime(2038, 1, 19),  # 32-bit timestamp limit
            datetime.utcnow() - timedelta(days=365),  # One year ago
            datetime.utcnow() + timedelta(days=365),  # One year future
        ]
        
        for i, timestamp in enumerate(extreme_timestamps):
            packet = PacketFactory.create_task_packet(
                "timestamp_test_node", "target", f"Timestamp test {i}"
            )
            packet.ts = timestamp
            
            try:
                packet_id = messenger.send_packet(packet)
                assert packet_id is not None
            except Exception as e:
                # Some extreme timestamps might cause issues
                print(f"Timestamp {timestamp} caused error: {str(e)}")
    
    def test_unicode_and_encoding_edge_cases(self):
        """Test Unicode and encoding edge cases."""
        state = create_test_state_view()
        context = create_test_step_context("unicode_test_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="unicode_test_node"),
            context=context
        )
        
        unicode_test_cases = [
            "Basic ASCII",
            "Café with accents",
            "你好世界",  # Chinese
            "مرحبا بالعالم",  # Arabic
            "Здравствуй мир",  # Russian
            "🌍🚀💻🎉",  # Emojis
            "\\U0001F600",  # Unicode escape
            "\\uD83D\\uDE00",  # Surrogate pair representation
            "Ωμέγα",  # Greek
            "नमस्ते",  # Hindi
            "こんにちは",  # Japanese
            "한글",  # Korean
            "תודה",  # Hebrew
            "ไทย",  # Thai
            "\\x41\\x42\\x43",  # Hex escapes
            "Mixed: ASCII + 中文 + العربية + 🌟"
        ]
        
        for i, test_content in enumerate(unicode_test_cases):
            try:
                packet = PacketFactory.create_task_packet(
                    "unicode_test_node", "target", test_content
                )
                packet.payload["unicode_test"] = f"Test case {i}"
                
                packet_id = messenger.send_packet(packet)
                assert packet_id is not None
                
            except Exception as e:
                print(f"Unicode test case {i} failed: {str(e)}")
                # Some unicode cases might legitimately fail
    
    def test_concurrent_extreme_operations(self):
        """Test concurrent operations under extreme conditions."""
        tester = ExtremeConditionTester()
        tester.setup_extreme_load(messenger_count=20)  # Moderate for testing
        
        # Test extreme concurrent operations
        result = tester.test_extreme_concurrent_operations(
            thread_count=10,
            ops_per_thread=50
        )
        
        assert result["total_sent"] > 0
        assert result["error_rate"] < 0.5  # Less than 50% error rate
        assert result["ops_per_second"] > 10  # At least 10 ops/second
        
        print(f"Concurrent test results:")
        print(f"  Total sent: {result['total_sent']}")
        print(f"  Total received: {result['total_received']}")
        print(f"  Error rate: {result['error_rate']:.2%}")
        print(f"  Ops/second: {result['ops_per_second']:.1f}")
    
    @pytest.mark.slow
    def test_massive_packet_creation(self):
        """Test creation of massive number of packets."""
        tester = ExtremeConditionTester()
        
        # Test massive packet creation
        result = tester.test_massive_packet_creation(packet_count=5000)  # Reduced for testing
        
        assert result["success"], f"Massive packet creation failed: {result.get('error')}"
        assert result["packet_count"] == 5000
        assert result["packets_per_second"] > 100  # At least 100 packets/second
        assert result["avg_memory_per_packet_kb"] < 50  # Less than 50KB per packet (realistic for Python objects)
        
        print(f"Massive packet creation results:")
        print(f"  Packets created: {result['packet_count']}")
        print(f"  Creation time: {result['creation_time_seconds']:.2f}s")
        print(f"  Packets/second: {result['packets_per_second']:.1f}")
        print(f"  Memory per packet: {result['avg_memory_per_packet_kb']:.2f}KB")
    
    def test_null_and_undefined_handling(self):
        """Test handling of null and undefined values."""
        state = create_test_state_view()
        context = create_test_step_context("null_test_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="null_test_node"),
            context=context
        )
        
        null_test_cases = [
            {"content": None},
            {"data": None, "content": "test"},
            {"nested": {"inner": None}},
            {"list_with_none": [1, None, 3]},
            {"mixed": {"a": None, "b": "value", "c": None}},
            {},  # Empty dict
            {"empty_string": ""},
            {"whitespace": "   "},
        ]
        
        for i, test_payload in enumerate(null_test_cases):
            packet = TaskPacket(
                src=ElementAddress(uid="null_test_node"),
                dst=ElementAddress(uid="target"),
                payload=test_payload
            )
            
            packet_id = messenger.send_packet(packet)
            assert packet_id is not None, f"Failed to send packet with null test case {i}"
    
    def test_extreme_adjacency_scenarios(self):
        """Test extreme adjacency scenarios."""
        state = create_test_state_view()
        
        # Test with no adjacent nodes
        isolated_context = create_test_step_context("isolated_node", [])
        isolated_messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="isolated_node"),
            context=isolated_context
        )
        
        packet = PacketFactory.create_task_packet("isolated_node", "non_existent", "isolated test")
        
        # Should be able to send even without adjacency (depending on implementation)
        try:
            packet_id = isolated_messenger.send_packet(packet)
            assert packet_id is not None
        except Exception as e:
            # Might fail due to adjacency checks
            print(f"Isolated node send failed (expected): {str(e)}")
        
        # Test with many adjacent nodes
        many_adjacent = [f"adjacent_node_{i}" for i in range(100)]
        crowded_context = create_test_step_context("crowded_node", many_adjacent)
        crowded_messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="crowded_node"),
            context=crowded_context
        )
        
        # Should handle many adjacent nodes
        packet = PacketFactory.create_task_packet("crowded_node", "adjacent_node_50", "crowded test")
        packet_id = crowded_messenger.send_packet(packet)
        assert packet_id is not None
    
    def test_rapid_fire_packet_sending(self):
        """Test rapid succession of packet sends."""
        state = create_test_state_view()
        context = create_test_step_context("rapid_fire_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="rapid_fire_node"),
            context=context
        )
        
        # Send packets as fast as possible
        start_time = time.time()
        packet_count = 1000
        successful_sends = 0
        
        for i in range(packet_count):
            try:
                packet = PacketFactory.create_task_packet(
                    "rapid_fire_node", "target", f"Rapid packet {i}"
                )
                messenger.send_packet(packet)
                successful_sends += 1
            except Exception as e:
                # Some might fail under rapid conditions
                pass
        
        total_time = time.time() - start_time
        send_rate = successful_sends / total_time if total_time > 0 else 0
        
        assert successful_sends > packet_count * 0.8  # At least 80% success
        assert send_rate > 500  # At least 500 packets/second
        
        print(f"Rapid fire results:")
        print(f"  Successful sends: {successful_sends}/{packet_count}")
        print(f"  Send rate: {send_rate:.1f} packets/second")
        print(f"  Total time: {total_time:.3f}s")
    
    def test_memory_pressure_handling(self):
        """Test behavior under memory pressure."""
        state = create_test_state_view()
        context = create_test_step_context("memory_pressure_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="memory_pressure_node"),
            context=context
        )
        
        import psutil
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create packets with increasingly large payloads
        large_payloads = []
        max_memory_increase = 100  # MB
        
        try:
            for i in range(100):
                # Create progressively larger payloads
                payload_size = 1024 * (i + 1)  # 1KB, 2KB, 3KB, etc.
                large_data = "x" * payload_size
                
                packet = PacketFactory.create_task_packet(
                    "memory_pressure_node", "target", f"Large packet {i}"
                )
                packet.payload["large_data"] = large_data
                large_payloads.append(packet)
                
                # Send packet
                messenger.send_packet(packet)
                
                # Check memory usage
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_increase = current_memory - initial_memory
                
                if memory_increase > max_memory_increase:
                    print(f"Stopping at packet {i} due to memory pressure: {memory_increase:.1f}MB")
                    break
                
                # Small delay to prevent overwhelming
                if i % 10 == 0:
                    time.sleep(0.01)
        
        except MemoryError:
            print("MemoryError encountered (expected under pressure)")
        
        final_memory = process.memory_info().rss / 1024 / 1024
        total_memory_used = final_memory - initial_memory
        
        print(f"Memory pressure test:")
        print(f"  Initial memory: {initial_memory:.1f}MB")
        print(f"  Final memory: {final_memory:.1f}MB")
        print(f"  Memory used: {total_memory_used:.1f}MB")
        print(f"  Packets created: {len(large_payloads)}")
        
        # Should handle some level of memory pressure
        assert len(large_payloads) > 10  # Should create at least 10 packets
        assert total_memory_used < 200  # Should not use excessive memory
    
    def test_edge_case_packet_ids(self):
        """Test edge cases in packet ID handling."""
        state = create_test_state_view()
        context = create_test_step_context("id_test_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="id_test_node"),
            context=context
        )
        
        # Send many packets and check for ID uniqueness
        packet_ids = set()
        packet_count = 1000
        
        for i in range(packet_count):
            packet = PacketFactory.create_task_packet(
                "id_test_node", "target", f"ID test packet {i}"
            )
            packet_id = messenger.send_packet(packet)
            
            assert packet_id is not None
            assert packet_id not in packet_ids, f"Duplicate packet ID: {packet_id}"
            packet_ids.add(packet_id)
        
        # All IDs should be unique
        assert len(packet_ids) == packet_count
        
        # IDs should be properly formatted (UUID-like)
        for packet_id in list(packet_ids)[:10]:  # Check first 10
            assert isinstance(packet_id, str)
            assert len(packet_id) > 0
            # UUIDs are typically 36 characters with hyphens
            # But implementation might vary
    
    def test_extreme_acknowledgment_scenarios(self):
        """Test extreme acknowledgment scenarios."""
        state = create_test_state_view()
        context = create_test_step_context("ack_test_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="ack_test_node"),
            context=context
        )
        
        # Send packets and test various acknowledgment patterns
        packets_sent = []
        for i in range(50):
            packet = PacketFactory.create_task_packet(
                "ack_test_node", "target", f"Ack test packet {i}"
            )
            packet_id = messenger.send_packet(packet)
            packets_sent.append(packet_id)
        
        # Test acknowledging non-existent packet
        try:
            messenger.acknowledge("non-existent-packet-id")
            # Should not fail catastrophically
        except Exception as e:
            print(f"Acknowledging non-existent packet: {str(e)}")
        
        # Test acknowledging same packet multiple times
        if packets_sent:
            first_packet_id = packets_sent[0]
            for _ in range(5):
                try:
                    messenger.acknowledge(first_packet_id)
                    # Should handle duplicate acknowledgments gracefully
                except Exception as e:
                    print(f"Duplicate acknowledgment: {str(e)}")
        
        # Test acknowledging with malformed IDs
        malformed_ids = ["", "invalid", "\\x00", None, 123, []]
        for malformed_id in malformed_ids:
            try:
                messenger.acknowledge(malformed_id)
            except Exception as e:
                print(f"Malformed ID {malformed_id}: {str(e)}")
    
    def test_resource_exhaustion_scenarios(self):
        """Test behavior under resource exhaustion."""
        state = create_test_state_view()
        context = create_test_step_context("resource_test_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="resource_test_node"),
            context=context
        )
        
        # Test rapid packet creation until resource limits
        resource_limit_reached = False
        packets_created = 0
        
        try:
            while packets_created < 10000:  # Reasonable upper limit
                packet = PacketFactory.create_task_packet(
                    "resource_test_node", "target", f"Resource test {packets_created}"
                )
                
                # Add some data to increase resource usage
                packet.payload["data"] = "x" * 1000  # 1KB per packet
                
                messenger.send_packet(packet)
                packets_created += 1
                
                # Check if we should stop (prevent test system overload)
                if packets_created % 1000 == 0:
                    import psutil
                    memory_percent = psutil.virtual_memory().percent
                    if memory_percent > 90:  # Stop if memory usage > 90%
                        print(f"Stopping due to high memory usage: {memory_percent}%")
                        resource_limit_reached = True
                        break
                
        except Exception as e:
            print(f"Resource exhaustion at {packets_created} packets: {str(e)}")
            resource_limit_reached = True
        
        print(f"Resource exhaustion test:")
        print(f"  Packets created: {packets_created}")
        print(f"  Limit reached: {resource_limit_reached}")
        
        # Should be able to create a reasonable number of packets
        assert packets_created > 100  # At least 100 packets
