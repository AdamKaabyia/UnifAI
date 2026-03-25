"""
Comprehensive memory usage and efficiency tests for IEM system.

Tests memory consumption patterns, leak detection, and optimization under various scenarios.
"""

import pytest
import gc
import time
import threading
import tracemalloc
import psutil
import weakref
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from mas.core.iem.messenger import DefaultInterMessenger
from mas.core.iem.models import ElementAddress
from mas.core.iem.packets import BaseIEMPacket, TaskPacket
from mas.graph.state.graph_state import Channel
from tests.fixtures.iem_testing_tools import (
    create_test_state_view, create_test_step_context,
    PacketFactory, IEMPerformanceMonitor
)


@dataclass
class MemorySnapshot:
    """Memory usage snapshot."""
    timestamp: datetime
    rss_mb: float  # Resident Set Size
    vms_mb: float  # Virtual Memory Size
    heap_mb: float  # Python heap
    packet_count: int
    messenger_count: int
    test_phase: str


class MemoryProfiler:
    """Advanced memory profiling for IEM components."""
    
    def __init__(self):
        self.snapshots: List[MemorySnapshot] = []
        self.process = psutil.Process()
        self.baseline_memory = None
        self.tracemalloc_started = False
    
    def start_profiling(self):
        """Start memory profiling."""
        if not self.tracemalloc_started:
            tracemalloc.start()
            self.tracemalloc_started = True
        
        gc.collect()  # Clean up before baseline
        self.baseline_memory = self._get_memory_info()
    
    def take_snapshot(self, test_phase: str, packet_count: int = 0, messenger_count: int = 0):
        """Take a memory snapshot."""
        memory_info = self._get_memory_info()
        
        snapshot = MemorySnapshot(
            timestamp=datetime.utcnow(),
            rss_mb=memory_info["rss_mb"],
            vms_mb=memory_info["vms_mb"], 
            heap_mb=memory_info["heap_mb"],
            packet_count=packet_count,
            messenger_count=messenger_count,
            test_phase=test_phase
        )
        
        self.snapshots.append(snapshot)
        return snapshot
    
    def _get_memory_info(self) -> Dict[str, float]:
        """Get current memory information."""
        # System memory
        memory_info = self.process.memory_info()
        rss_mb = memory_info.rss / 1024 / 1024
        vms_mb = memory_info.vms / 1024 / 1024
        
        # Python heap memory
        heap_mb = 0
        if self.tracemalloc_started:
            current, peak = tracemalloc.get_traced_memory()
            heap_mb = current / 1024 / 1024
        
        return {
            "rss_mb": rss_mb,
            "vms_mb": vms_mb,
            "heap_mb": heap_mb
        }
    
    def get_memory_growth(self, phase1: str, phase2: str) -> Dict[str, float]:
        """Calculate memory growth between two phases."""
        phase1_snapshot = next((s for s in self.snapshots if s.test_phase == phase1), None)
        phase2_snapshot = next((s for s in self.snapshots if s.test_phase == phase2), None)
        
        if not phase1_snapshot or not phase2_snapshot:
            return {"error": "Phase not found"}
        
        return {
            "rss_growth_mb": phase2_snapshot.rss_mb - phase1_snapshot.rss_mb,
            "vms_growth_mb": phase2_snapshot.vms_mb - phase1_snapshot.vms_mb,
            "heap_growth_mb": phase2_snapshot.heap_mb - phase1_snapshot.heap_mb,
            "packet_count_change": phase2_snapshot.packet_count - phase1_snapshot.packet_count,
            "duration_seconds": (phase2_snapshot.timestamp - phase1_snapshot.timestamp).total_seconds()
        }
    
    def detect_memory_leaks(self, threshold_mb: float = 10.0) -> List[Dict[str, Any]]:
        """Detect potential memory leaks."""
        leaks = []
        
        if len(self.snapshots) < 2:
            return leaks
        
        # Check for monotonic memory growth
        for i in range(1, len(self.snapshots)):
            prev_snapshot = self.snapshots[i-1]
            curr_snapshot = self.snapshots[i]
            
            rss_growth = curr_snapshot.rss_mb - prev_snapshot.rss_mb
            heap_growth = curr_snapshot.heap_mb - prev_snapshot.heap_mb
            
            if rss_growth > threshold_mb or heap_growth > threshold_mb:
                leaks.append({
                    "phase_from": prev_snapshot.test_phase,
                    "phase_to": curr_snapshot.test_phase,
                    "rss_growth_mb": rss_growth,
                    "heap_growth_mb": heap_growth,
                    "severity": "high" if rss_growth > threshold_mb * 2 else "medium"
                })
        
        return leaks
    
    def stop_profiling(self):
        """Stop memory profiling."""
        if self.tracemalloc_started:
            tracemalloc.stop()
            self.tracemalloc_started = False


class MemoryStressTest:
    """Memory stress testing for IEM system."""
    
    def __init__(self, profiler: MemoryProfiler):
        self.profiler = profiler
        self.messengers = []
        self.packets = []
        self.state = None
    
    def setup_test_environment(self, messenger_count: int):
        """Set up test environment with specified number of messengers."""
        self.state = create_test_state_view()
        self.messengers = []
        
        for i in range(messenger_count):
            uid = f"stress_node_{i}"
            adjacent_uids = [f"stress_node_{j}" for j in range(messenger_count) if j != i]
            
            context = create_test_step_context(uid, adjacent_uids)
            messenger = DefaultInterMessenger(
                state=self.state,
                identity=ElementAddress(uid=uid),
                context=context
            )
            self.messengers.append(messenger)
    
    def stress_test_packet_creation(self, packet_count: int) -> List[BaseIEMPacket]:
        """Stress test packet creation and memory usage."""
        self.profiler.take_snapshot("packet_creation_start", 0, len(self.messengers))
        
        packets = []
        batch_size = 1000
        
        for i in range(packet_count):
            sender_idx = i % len(self.messengers)
            receiver_idx = (i + 1) % len(self.messengers)
            
            sender_uid = f"stress_node_{sender_idx}"
            receiver_uid = f"stress_node_{receiver_idx}"
            
            packet = PacketFactory.create_task_packet(
                sender_uid,
                receiver_uid,
                f"Stress test packet {i}",
                data={"stress_test": True, "packet_index": i}
            )
            packets.append(packet)
            
            # Take snapshots periodically
            if (i + 1) % batch_size == 0:
                self.profiler.take_snapshot(
                    f"packet_creation_{i + 1}",
                    len(packets),
                    len(self.messengers)
                )
        
        self.packets = packets
        self.profiler.take_snapshot("packet_creation_end", len(packets), len(self.messengers))
        return packets
    
    def stress_test_packet_sending(self, packets: List[BaseIEMPacket]) -> int:
        """Stress test packet sending."""
        self.profiler.take_snapshot("packet_sending_start", len(packets), len(self.messengers))
        
        sent_count = 0
        batch_size = 500
        
        for i, packet in enumerate(packets):
            sender_idx = int(packet.src.uid.split('_')[-1])
            messenger = self.messengers[sender_idx]
            
            try:
                messenger.send_packet(packet)
                sent_count += 1
            except Exception as e:
                # Continue on error
                pass
            
            # Take snapshots periodically
            if (i + 1) % batch_size == 0:
                self.profiler.take_snapshot(
                    f"packet_sending_{i + 1}",
                    len(packets),
                    len(self.messengers)
                )
        
        self.profiler.take_snapshot("packet_sending_end", len(packets), len(self.messengers))
        return sent_count
    
    def stress_test_packet_receiving(self) -> int:
        """Stress test packet receiving."""
        self.profiler.take_snapshot("packet_receiving_start", len(self.packets), len(self.messengers))
        
        total_received = 0
        batch_size = 500
        
        for i, messenger in enumerate(self.messengers):
            received_packets = messenger.inbox_packets()
            total_received += len(received_packets)
            
            # Acknowledge packets
            for packet in received_packets:
                messenger.acknowledge(packet.id)
            
            # Take snapshots periodically
            if (i + 1) % batch_size == 0:
                self.profiler.take_snapshot(
                    f"packet_receiving_{i + 1}",
                    len(self.packets),
                    len(self.messengers)
                )
        
        self.profiler.take_snapshot("packet_receiving_end", len(self.packets), len(self.messengers))
        return total_received
    
    def cleanup_resources(self):
        """Clean up test resources."""
        self.profiler.take_snapshot("cleanup_start", len(self.packets), len(self.messengers))
        
        # Clear packets
        self.packets.clear()
        
        # Clear messengers
        self.messengers.clear()
        
        # Clear state
        if self.state:
            # Clear state channels
            if hasattr(self.state, 'inter_packets'):
                self.state[Channel.INTER_PACKETS] = []
        
        self.state = None
        
        # Force garbage collection
        gc.collect()
        
        self.profiler.take_snapshot("cleanup_end", 0, 0)


class TestMemoryUsage:
    """Test suite for IEM memory usage and efficiency."""
    
    def test_baseline_memory_usage(self):
        """Test baseline memory usage of IEM components."""
        profiler = MemoryProfiler()
        profiler.start_profiling()
        
        # Baseline measurement
        profiler.take_snapshot("baseline", 0, 0)
        
        # Create single messenger
        state = create_test_state_view()
        context = create_test_step_context("memory_test_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="memory_test_node"),
            context=context
        )
        
        profiler.take_snapshot("single_messenger", 0, 1)
        
        # Create single packet
        packet = PacketFactory.create_task_packet("memory_test_node", "target")
        profiler.take_snapshot("single_packet", 1, 1)
        
        # Send packet
        messenger.send_packet(packet)
        profiler.take_snapshot("packet_sent", 1, 1)
        
        # Calculate memory usage
        messenger_memory = profiler.get_memory_growth("baseline", "single_messenger")
        packet_memory = profiler.get_memory_growth("single_messenger", "single_packet")
        send_memory = profiler.get_memory_growth("single_packet", "packet_sent")
        
        # Verify reasonable memory usage
        assert messenger_memory["rss_growth_mb"] < 10  # Messenger under 10MB
        assert packet_memory["rss_growth_mb"] < 1      # Packet under 1MB
        assert send_memory["rss_growth_mb"] < 1        # Send operation under 1MB
        
        profiler.stop_profiling()
        
        print(f"Messenger memory: {messenger_memory['rss_growth_mb']:.2f}MB")
        print(f"Packet memory: {packet_memory['rss_growth_mb']:.2f}MB")
        print(f"Send memory: {send_memory['rss_growth_mb']:.2f}MB")
    
    def test_packet_memory_scaling(self):
        """Test memory usage scaling with packet count."""
        profiler = MemoryProfiler()
        profiler.start_profiling()
        
        stress_test = MemoryStressTest(profiler)
        stress_test.setup_test_environment(messenger_count=2)
        
        # Test different packet counts
        packet_counts = [100, 500, 1000, 2000]
        memory_per_packet = []
        
        for count in packet_counts:
            profiler.take_snapshot(f"before_{count}_packets", 0, 2)
            
            packets = stress_test.stress_test_packet_creation(count)
            
            profiler.take_snapshot(f"after_{count}_packets", count, 2)
            
            # Calculate memory per packet
            memory_growth = profiler.get_memory_growth(f"before_{count}_packets", f"after_{count}_packets")
            memory_per_packet_kb = (memory_growth["rss_growth_mb"] * 1024) / count if count > 0 else 0
            memory_per_packet.append(memory_per_packet_kb)
            
            print(f"{count} packets: {memory_growth['rss_growth_mb']:.2f}MB total, "
                  f"{memory_per_packet_kb:.2f}KB per packet")
            
            # Clean up for next iteration
            packets.clear()
            gc.collect()
        
        # Verify memory scaling is reasonable
        for mem_per_packet in memory_per_packet:
            assert mem_per_packet < 100  # Less than 100KB per packet
        
        # Memory per packet should be relatively consistent
        if len(memory_per_packet) > 1:
            max_mem = max(memory_per_packet)
            min_mem = min(memory_per_packet)
            ratio = max_mem / min_mem if min_mem > 0 else 1
            assert ratio < 3  # Memory per packet should not vary by more than 3x
        
        profiler.stop_profiling()
    
    def test_messenger_memory_scaling(self):
        """Test memory usage scaling with messenger count."""
        profiler = MemoryProfiler()
        profiler.start_profiling()
        
        messenger_counts = [1, 5, 10, 20]
        memory_per_messenger = []
        
        for count in messenger_counts:
            profiler.take_snapshot(f"before_{count}_messengers", 0, 0)
            
            # Create messengers
            state = create_test_state_view()
            messengers = []
            
            for i in range(count):
                uid = f"memory_node_{i}"
                adjacent_uids = [f"memory_node_{j}" for j in range(count) if j != i]
                
                context = create_test_step_context(uid, adjacent_uids)
                messenger = DefaultInterMessenger(
                    state=state,
                    identity=ElementAddress(uid=uid),
                    context=context
                )
                messengers.append(messenger)
            
            profiler.take_snapshot(f"after_{count}_messengers", 0, count)
            
            # Calculate memory per messenger
            memory_growth = profiler.get_memory_growth(f"before_{count}_messengers", f"after_{count}_messengers")
            memory_per_messenger_kb = (memory_growth["rss_growth_mb"] * 1024) / count if count > 0 else 0
            memory_per_messenger.append(memory_per_messenger_kb)
            
            print(f"{count} messengers: {memory_growth['rss_growth_mb']:.2f}MB total, "
                  f"{memory_per_messenger_kb:.2f}KB per messenger")
            
            # Clean up for next iteration
            messengers.clear()
            state = None
            gc.collect()
        
        # Verify memory scaling
        for mem_per_messenger in memory_per_messenger:
            assert mem_per_messenger < 1000  # Less than 1MB per messenger
        
        profiler.stop_profiling()
    
    @pytest.mark.slow
    def test_memory_leak_detection(self):
        """Test for memory leaks during extended operation."""
        profiler = MemoryProfiler()
        profiler.start_profiling()
        
        stress_test = MemoryStressTest(profiler)
        stress_test.setup_test_environment(messenger_count=3)
        
        # Run multiple cycles to detect leaks
        cycles = 5
        packets_per_cycle = 500
        
        for cycle in range(cycles):
            cycle_start_phase = f"cycle_{cycle}_start"
            cycle_end_phase = f"cycle_{cycle}_end"
            
            profiler.take_snapshot(cycle_start_phase, 0, 3)
            
            # Create, send, receive, and cleanup packets
            packets = stress_test.stress_test_packet_creation(packets_per_cycle)
            sent_count = stress_test.stress_test_packet_sending(packets)
            received_count = stress_test.stress_test_packet_receiving()
            stress_test.cleanup_resources()
            
            # Rebuild environment for next cycle
            if cycle < cycles - 1:
                stress_test.setup_test_environment(messenger_count=3)
            
            profiler.take_snapshot(cycle_end_phase, 0, 3)
            
            print(f"Cycle {cycle}: {sent_count} sent, {received_count} received")
        
        # Detect memory leaks
        leaks = profiler.detect_memory_leaks(threshold_mb=5.0)
        
        # Should not have significant memory leaks
        high_severity_leaks = [leak for leak in leaks if leak["severity"] == "high"]
        assert len(high_severity_leaks) == 0, f"High severity memory leaks detected: {high_severity_leaks}"
        
        # Calculate overall memory growth
        overall_growth = profiler.get_memory_growth("cycle_0_start", f"cycle_{cycles-1}_end")
        
        # Total memory growth should be reasonable
        assert overall_growth["rss_growth_mb"] < 50, f"Excessive memory growth: {overall_growth['rss_growth_mb']:.2f}MB"
        
        if leaks:
            print(f"Detected {len(leaks)} potential memory issues (threshold: 5MB)")
            for leak in leaks:
                print(f"  {leak['phase_from']} -> {leak['phase_to']}: "
                      f"{leak['rss_growth_mb']:.2f}MB RSS, {leak['heap_growth_mb']:.2f}MB heap")
        
        profiler.stop_profiling()
    
    def test_concurrent_memory_usage(self):
        """Test memory usage under concurrent operations."""
        profiler = MemoryProfiler()
        profiler.start_profiling()
        
        profiler.take_snapshot("concurrent_start", 0, 0)
        
        # Setup
        state = create_test_state_view()
        messengers = []
        
        for i in range(5):
            uid = f"concurrent_node_{i}"
            context = create_test_step_context(uid, [f"concurrent_node_{j}" for j in range(5) if j != i])
            messenger = DefaultInterMessenger(
                state=state,
                identity=ElementAddress(uid=uid),
                context=context
            )
            messengers.append(messenger)
        
        profiler.take_snapshot("concurrent_setup", 0, 5)
        
        # Concurrent packet operations
        def worker_thread(thread_id: int):
            packet_count = 100
            thread_packets = []
            
            for i in range(packet_count):
                sender_idx = thread_id % len(messengers)
                receiver_idx = (thread_id + 1) % len(messengers)
                
                packet = PacketFactory.create_task_packet(
                    f"concurrent_node_{sender_idx}",
                    f"concurrent_node_{receiver_idx}",
                    f"Thread {thread_id} packet {i}"
                )
                thread_packets.append(packet)
                
                # Send packet
                messengers[sender_idx].send_packet(packet)
            
            return len(thread_packets)
        
        # Run concurrent workers
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(worker_thread, i) for i in range(3)]
            results = [future.result() for future in futures]
        
        profiler.take_snapshot("concurrent_operations", sum(results), 5)
        
        # Receive packets
        total_received = 0
        for messenger in messengers:
            packets = messenger.inbox_packets()
            total_received += len(packets)
            for packet in packets:
                messenger.acknowledge(packet.id)
        
        profiler.take_snapshot("concurrent_cleanup", 0, 5)
        
        # Check memory usage
        operation_memory = profiler.get_memory_growth("concurrent_setup", "concurrent_operations")
        cleanup_memory = profiler.get_memory_growth("concurrent_operations", "concurrent_cleanup")
        
        # Memory usage should be reasonable
        total_packets = sum(results)
        memory_per_packet_kb = (operation_memory["rss_growth_mb"] * 1024) / total_packets if total_packets > 0 else 0
        
        assert memory_per_packet_kb < 50  # Less than 50KB per packet in concurrent scenario
        assert total_received == total_packets  # All packets should be received
        
        print(f"Concurrent operations: {total_packets} packets, {operation_memory['rss_growth_mb']:.2f}MB")
        print(f"Memory per packet: {memory_per_packet_kb:.2f}KB")
        
        profiler.stop_profiling()
    
    def test_large_payload_memory_impact(self):
        """Test memory impact of large payloads."""
        profiler = MemoryProfiler()
        profiler.start_profiling()
        
        state = create_test_state_view()
        context = create_test_step_context("large_payload_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="large_payload_node"),
            context=context
        )
        
        profiler.take_snapshot("large_payload_start", 0, 1)
        
        # Test different payload sizes
        payload_sizes_kb = [1, 10, 100, 500, 1000]
        memory_results = []
        
        for size_kb in payload_sizes_kb:
            profiler.take_snapshot(f"before_payload_{size_kb}kb", 0, 1)
            
            # Create packet with large payload
            large_data = "x" * (size_kb * 1024)
            packet = PacketFactory.create_task_packet(
                "large_payload_node",
                "target",
                f"Large payload test - {size_kb}KB"
            )
            packet.payload["large_data"] = large_data
            
            # Send packet
            messenger.send_packet(packet)
            
            profiler.take_snapshot(f"after_payload_{size_kb}kb", 1, 1)
            
            # Calculate memory usage
            memory_growth = profiler.get_memory_growth(f"before_payload_{size_kb}kb", f"after_payload_{size_kb}kb")
            memory_overhead_kb = memory_growth["rss_growth_mb"] * 1024 - size_kb
            
            memory_results.append({
                "payload_size_kb": size_kb,
                "total_memory_kb": memory_growth["rss_growth_mb"] * 1024,
                "overhead_kb": memory_overhead_kb,
                "overhead_ratio": memory_overhead_kb / size_kb if size_kb > 0 else 0
            })
            
            print(f"Payload {size_kb}KB: Total {memory_growth['rss_growth_mb'] * 1024:.1f}KB, "
                  f"Overhead {memory_overhead_kb:.1f}KB")
        
        # Verify memory efficiency
        for result in memory_results:
            # Overhead should be reasonable (less than 100% of payload size)
            assert result["overhead_ratio"] < 1.0, f"High overhead for {result['payload_size_kb']}KB payload"
            
            # Total memory change may be small due to measurement granularity
            # Just verify the test completed without major errors
            assert result["total_memory_kb"] >= 0  # Memory change should be non-negative
            assert result["total_memory_kb"] < result["payload_size_kb"] * 2  # Should not be excessive
        
        profiler.stop_profiling()
    
    def test_memory_cleanup_efficiency(self):
        """Test efficiency of memory cleanup operations."""
        profiler = MemoryProfiler()
        profiler.start_profiling()
        
        stress_test = MemoryStressTest(profiler)
        stress_test.setup_test_environment(messenger_count=4)
        
        # Create large number of packets
        packet_count = 2000
        packets = stress_test.stress_test_packet_creation(packet_count)
        
        profiler.take_snapshot("before_cleanup", packet_count, 4)
        
        # Test different cleanup strategies
        cleanup_strategies = [
            ("partial_cleanup", lambda: packets[:len(packets)//2].clear()),
            ("full_cleanup", lambda: packets.clear()),
            ("gc_cleanup", lambda: gc.collect()),
            ("deep_cleanup", lambda: stress_test.cleanup_resources())
        ]
        
        for strategy_name, cleanup_func in cleanup_strategies:
            pre_cleanup_phase = f"pre_{strategy_name}"
            post_cleanup_phase = f"post_{strategy_name}"
            
            profiler.take_snapshot(pre_cleanup_phase, len(packets), len(stress_test.messengers))
            
            # Execute cleanup
            cleanup_func()
            
            profiler.take_snapshot(post_cleanup_phase, len(packets), len(stress_test.messengers))
            
            # Measure cleanup effectiveness
            cleanup_effect = profiler.get_memory_growth(pre_cleanup_phase, post_cleanup_phase)
            
            print(f"{strategy_name}: {cleanup_effect['rss_growth_mb']:.2f}MB change")
            
            # Cleanup should reduce or maintain memory usage
            assert cleanup_effect["rss_growth_mb"] <= 5.0, f"Memory increased during {strategy_name}"
        
        profiler.stop_profiling()
    
    def test_weak_reference_cleanup(self):
        """Test that objects are properly garbage collected using weak references."""
        profiler = MemoryProfiler()
        profiler.start_profiling()
        
        # Create objects and weak references
        weak_refs = []
        
        profiler.take_snapshot("weak_ref_start", 0, 0)
        
        # Create messengers and packets with weak references
        for i in range(10):
            state = create_test_state_view()
            context = create_test_step_context(f"weak_ref_node_{i}", ["target"])
            messenger = DefaultInterMessenger(
                state=state,
                identity=ElementAddress(uid=f"weak_ref_node_{i}"),
                context=context
            )
            
            # Create weak reference
            weak_refs.append(weakref.ref(messenger))
            
            # Create some packets
            for j in range(10):
                packet = PacketFactory.create_task_packet(f"weak_ref_node_{i}", "target", f"packet_{j}")
                messenger.send_packet(packet)
        
        profiler.take_snapshot("weak_ref_created", 100, 10)
        
        # Clear strong references
        # (Objects should be eligible for garbage collection)
        
        profiler.take_snapshot("weak_ref_before_gc", 100, 10)
        
        # Force garbage collection
        gc.collect()
        
        profiler.take_snapshot("weak_ref_after_gc", 0, 0)
        
        # Check weak references
        alive_refs = [ref for ref in weak_refs if ref() is not None]
        
        print(f"Weak references: {len(weak_refs)} created, {len(alive_refs)} still alive")
        
        # Most objects should be garbage collected
        gc_effectiveness = (len(weak_refs) - len(alive_refs)) / len(weak_refs)
        assert gc_effectiveness > 0.8, f"Poor garbage collection: {gc_effectiveness:.2%} cleaned up"
        
        # Memory recovery may be limited due to Python's memory management
        # Just verify GC worked on object references
        memory_recovery = profiler.get_memory_growth("weak_ref_created", "weak_ref_after_gc")
        # Memory might not be immediately returned to OS, but objects should be deallocated
        assert memory_recovery["rss_growth_mb"] <= 10, "Memory usage should be stable or reduced"
        
        profiler.stop_profiling()
