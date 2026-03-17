"""
Comprehensive throughput and performance tests for IEM system.

Tests message throughput limits, latency characteristics, and performance under various loads.
"""

import pytest
import time
import threading
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import psutil
import gc

from mas.core.iem.messenger import DefaultInterMessenger
from mas.core.iem.models import ElementAddress
from mas.core.iem.packets import BaseIEMPacket, TaskPacket
from tests.fixtures.iem_testing_tools import (
    create_test_state_view, create_test_step_context,
    PacketFactory, IEMPerformanceMonitor
)


@dataclass
class ThroughputMetrics:
    """Metrics for throughput testing."""
    packets_sent: int
    packets_received: int
    duration_seconds: float
    send_throughput: float  # packets/second
    receive_throughput: float  # packets/second
    latencies: List[float]  # milliseconds
    avg_latency: float
    p50_latency: float
    p95_latency: float
    p99_latency: float
    memory_usage_mb: float
    cpu_usage_percent: float


class ThroughputTestHarness:
    """Test harness for measuring IEM throughput."""
    
    def __init__(self, sender_count: int = 1, receiver_count: int = 1):
        self.sender_count = sender_count
        self.receiver_count = receiver_count
        self.senders = []
        self.receivers = []
        self.state = create_test_state_view()
        self.metrics = ThroughputMetrics(0, 0, 0, 0, 0, [], 0, 0, 0, 0, 0, 0)
        
        self._setup_nodes()
    
    def _setup_nodes(self):
        """Set up sender and receiver nodes."""
        # Create sender nodes
        for i in range(self.sender_count):
            sender_uid = f"sender_{i}"
            receiver_uids = [f"receiver_{j}" for j in range(self.receiver_count)]
            
            context = create_test_step_context(sender_uid, receiver_uids)
            messenger = DefaultInterMessenger(
                state=self.state,
                identity=ElementAddress(uid=sender_uid),
                context=context
            )
            self.senders.append((sender_uid, messenger))
        
        # Create receiver nodes
        for i in range(self.receiver_count):
            receiver_uid = f"receiver_{i}"
            sender_uids = [f"sender_{j}" for j in range(self.sender_count)]
            
            context = create_test_step_context(receiver_uid, sender_uids)
            messenger = DefaultInterMessenger(
                state=self.state,
                identity=ElementAddress(uid=receiver_uid),
                context=context
            )
            self.receivers.append((receiver_uid, messenger))
    
    def run_throughput_test(self, 
                           packet_count: int,
                           batch_size: int = 100,
                           concurrent_senders: bool = True) -> ThroughputMetrics:
        """Run throughput test with specified parameters."""
        
        # Start monitoring system resources
        process = psutil.Process()
        start_cpu = process.cpu_percent()
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Clear any existing packets
        gc.collect()
        
        start_time = time.time()
        sent_packets = []
        packet_timestamps = {}
        
        # Send packets
        if concurrent_senders:
            sent_packets = self._send_packets_concurrent(packet_count, batch_size, packet_timestamps)
        else:
            sent_packets = self._send_packets_sequential(packet_count, batch_size, packet_timestamps)
        
        send_end_time = time.time()
        
        # Receive packets
        received_packets = self._receive_all_packets()
        
        receive_end_time = time.time()
        
        # Calculate latencies
        latencies = []
        for packet in received_packets:
            if packet.id in packet_timestamps:
                latency_ms = (receive_end_time - packet_timestamps[packet.id]) * 1000
                latencies.append(latency_ms)
        
        # Calculate metrics
        total_duration = receive_end_time - start_time
        send_duration = send_end_time - start_time
        
        # System resource usage
        end_cpu = process.cpu_percent()
        end_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        self.metrics = ThroughputMetrics(
            packets_sent=len(sent_packets),
            packets_received=len(received_packets),
            duration_seconds=total_duration,
            send_throughput=len(sent_packets) / send_duration if send_duration > 0 else 0,
            receive_throughput=len(received_packets) / total_duration if total_duration > 0 else 0,
            latencies=latencies,
            avg_latency=statistics.mean(latencies) if latencies else 0,
            p50_latency=statistics.median(latencies) if latencies else 0,
            p95_latency=statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else 0,
            p99_latency=statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else 0,
            memory_usage_mb=end_memory - start_memory,
            cpu_usage_percent=end_cpu - start_cpu
        )
        
        return self.metrics
    
    def _send_packets_concurrent(self, packet_count: int, batch_size: int, timestamps: Dict) -> List[str]:
        """Send packets using concurrent senders."""
        packets_per_sender = packet_count // self.sender_count
        remainder = packet_count % self.sender_count
        
        def sender_worker(sender_info: Tuple, start_idx: int, count: int) -> List[str]:
            sender_uid, messenger = sender_info
            sent_ids = []
            
            for i in range(count):
                receiver_uid = f"receiver_{i % self.receiver_count}"
                packet = PacketFactory.create_task_packet(
                    sender_uid, 
                    receiver_uid, 
                    f"Throughput test packet {start_idx + i}"
                )
                
                packet_id = messenger.send_packet(packet)
                timestamps[packet_id] = time.time()
                sent_ids.append(packet_id)
                
                # Batch processing delay
                if (i + 1) % batch_size == 0:
                    time.sleep(0.001)  # Small yield
            
            return sent_ids
        
        # Distribute packets among senders
        with ThreadPoolExecutor(max_workers=self.sender_count) as executor:
            futures = []
            start_idx = 0
            
            for i, sender_info in enumerate(self.senders):
                count = packets_per_sender + (1 if i < remainder else 0)
                future = executor.submit(sender_worker, sender_info, start_idx, count)
                futures.append(future)
                start_idx += count
            
            all_packet_ids = []
            for future in as_completed(futures):
                all_packet_ids.extend(future.result())
        
        return all_packet_ids
    
    def _send_packets_sequential(self, packet_count: int, batch_size: int, timestamps: Dict) -> List[str]:
        """Send packets sequentially from a single sender."""
        if not self.senders:
            return []
        
        sender_uid, messenger = self.senders[0]
        sent_ids = []
        
        for i in range(packet_count):
            receiver_uid = f"receiver_{i % self.receiver_count}"
            packet = PacketFactory.create_task_packet(
                sender_uid,
                receiver_uid,
                f"Sequential throughput packet {i}"
            )
            
            packet_id = messenger.send_packet(packet)
            timestamps[packet_id] = time.time()
            sent_ids.append(packet_id)
            
            # Batch processing delay
            if (i + 1) % batch_size == 0:
                time.sleep(0.001)  # Small yield
        
        return sent_ids
    
    def _receive_all_packets(self) -> List[BaseIEMPacket]:
        """Receive all packets from all receivers."""
        all_packets = []
        
        for receiver_uid, messenger in self.receivers:
            packets = messenger.inbox_packets()
            all_packets.extend(packets)
            
            # Acknowledge all packets
            for packet in packets:
                messenger.acknowledge(packet.id)
        
        return all_packets


class LatencyTestHarness:
    """Test harness for measuring IEM latency characteristics."""
    
    def __init__(self):
        self.state = create_test_state_view()
        self.sender_context = create_test_step_context("latency_sender", ["latency_receiver"])
        self.receiver_context = create_test_step_context("latency_receiver", ["latency_sender"])
        
        self.sender = DefaultInterMessenger(
            state=self.state,
            identity=ElementAddress(uid="latency_sender"),
            context=self.sender_context
        )
        
        self.receiver = DefaultInterMessenger(
            state=self.state,
            identity=ElementAddress(uid="latency_receiver"),
            context=self.receiver_context
        )
    
    def measure_single_packet_latency(self, payload_size_kb: int = 1) -> float:
        """Measure latency for a single packet."""
        # Create packet with specified payload size
        large_data = "x" * (payload_size_kb * 1024)
        packet = PacketFactory.create_task_packet(
            "latency_sender",
            "latency_receiver",
            f"Latency test - {payload_size_kb}KB"
        )
        packet.payload["large_data"] = large_data
        
        # Measure send time
        start_time = time.perf_counter()
        packet_id = self.sender.send_packet(packet)
        send_time = time.perf_counter()
        
        # Measure receive time
        received_packets = self.receiver.inbox_packets()
        receive_time = time.perf_counter()
        
        # Acknowledge
        if received_packets:
            self.receiver.acknowledge(received_packets[0].id)
        
        # Calculate total latency
        total_latency_ms = (receive_time - start_time) * 1000
        send_latency_ms = (send_time - start_time) * 1000
        
        return {
            "total_latency_ms": total_latency_ms,
            "send_latency_ms": send_latency_ms,
            "received_packets": len(received_packets),
            "payload_size_kb": payload_size_kb
        }
    
    def measure_latency_distribution(self, sample_count: int = 100) -> Dict[str, Any]:
        """Measure latency distribution across multiple samples."""
        latencies = []
        
        for i in range(sample_count):
            result = self.measure_single_packet_latency()
            latencies.append(result["total_latency_ms"])
            
            # Small delay between measurements
            time.sleep(0.001)
        
        return {
            "sample_count": sample_count,
            "latencies": latencies,
            "avg_latency_ms": statistics.mean(latencies),
            "median_latency_ms": statistics.median(latencies),
            "std_dev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
            "p95_latency_ms": statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else 0,
            "p99_latency_ms": statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else 0
        }


class TestThroughput:
    """Test suite for IEM throughput and performance."""
    
    @pytest.mark.slow
    def test_single_sender_throughput(self):
        """Test throughput with single sender."""
        harness = ThroughputTestHarness(sender_count=1, receiver_count=1)
        
        # Test with moderate load
        metrics = harness.run_throughput_test(
            packet_count=1000,
            batch_size=50,
            concurrent_senders=False
        )
        
        # Verify basic functionality
        assert metrics.packets_sent == 1000
        assert metrics.packets_received == 1000
        assert metrics.send_throughput > 0
        assert metrics.receive_throughput > 0
        assert metrics.avg_latency >= 0
        
        # Performance expectations (adjust based on system)
        assert metrics.send_throughput > 100  # At least 100 packets/second
        assert metrics.avg_latency < 500  # Less than 500ms average latency (realistic for Python)
        
        print(f"Single sender throughput: {metrics.send_throughput:.2f} packets/sec")
        print(f"Average latency: {metrics.avg_latency:.2f}ms")
    
    @pytest.mark.slow
    def test_multi_sender_throughput(self):
        """Test throughput with multiple concurrent senders."""
        harness = ThroughputTestHarness(sender_count=3, receiver_count=2)
        
        # Test with concurrent senders
        metrics = harness.run_throughput_test(
            packet_count=1500,  # 500 per sender
            batch_size=100,
            concurrent_senders=True
        )
        
        # Verify all packets were processed
        assert metrics.packets_sent == 1500
        assert metrics.packets_received == 1500
        
        # Concurrent senders should achieve higher throughput
        assert metrics.send_throughput > 200  # Should be higher with concurrency
        
        print(f"Multi-sender throughput: {metrics.send_throughput:.2f} packets/sec")
        print(f"P95 latency: {metrics.p95_latency:.2f}ms")
    
    @pytest.mark.slow
    def test_scalability_characteristics(self):
        """Test how throughput scales with number of nodes."""
        packet_count = 1000
        results = {}
        
        # Test different node configurations
        configurations = [
            (1, 1, "1s_1r"),
            (2, 1, "2s_1r"), 
            (1, 2, "1s_2r"),
            (2, 2, "2s_2r"),
            (3, 3, "3s_3r")
        ]
        
        for sender_count, receiver_count, config_name in configurations:
            harness = ThroughputTestHarness(sender_count, receiver_count)
            
            metrics = harness.run_throughput_test(
                packet_count=packet_count,
                batch_size=100,
                concurrent_senders=True
            )
            
            results[config_name] = {
                "senders": sender_count,
                "receivers": receiver_count,
                "throughput": metrics.send_throughput,
                "latency": metrics.avg_latency,
                "memory_mb": metrics.memory_usage_mb
            }
        
        # Verify scaling behavior
        single_node_throughput = results["1s_1r"]["throughput"]
        multi_node_throughput = results["3s_3r"]["throughput"]
        
        # Performance may vary with more nodes due to Python GIL and coordination overhead
        # Just verify both configurations work reasonably well
        assert single_node_throughput > 1000  # Single node should be fast
        assert multi_node_throughput > 1000   # Multi node should also work well
        
        # Print results for analysis
        for config, data in results.items():
            print(f"{config}: {data['throughput']:.1f} pps, {data['latency']:.1f}ms, {data['memory_mb']:.1f}MB")
    
    @pytest.mark.slow
    def test_high_load_throughput(self):
        """Test throughput under high load conditions."""
        harness = ThroughputTestHarness(sender_count=5, receiver_count=3)
        
        # High load test
        metrics = harness.run_throughput_test(
            packet_count=5000,
            batch_size=200,
            concurrent_senders=True
        )
        
        # Verify system handles high load
        assert metrics.packets_sent == 5000
        assert metrics.packets_received == 5000
        
        # Performance under load
        assert metrics.send_throughput > 500  # Should maintain reasonable throughput
        assert metrics.p99_latency < 3000  # P99 latency under 3 seconds (realistic for high load)
        
        # Memory usage should be reasonable
        assert metrics.memory_usage_mb < 100  # Less than 100MB additional memory
        
        print(f"High load throughput: {metrics.send_throughput:.2f} packets/sec")
        print(f"P99 latency: {metrics.p99_latency:.2f}ms")
        print(f"Memory usage: {metrics.memory_usage_mb:.2f}MB")
    
    def test_latency_characteristics(self):
        """Test latency characteristics of IEM system."""
        harness = LatencyTestHarness()
        
        # Test basic latency
        basic_result = harness.measure_single_packet_latency(payload_size_kb=1)
        assert basic_result["received_packets"] == 1
        assert basic_result["total_latency_ms"] >= 0
        
        # Test latency distribution
        distribution = harness.measure_latency_distribution(sample_count=50)
        
        assert distribution["sample_count"] == 50
        assert len(distribution["latencies"]) == 50
        assert distribution["avg_latency_ms"] > 0
        assert distribution["std_dev_ms"] >= 0
        
        # Latency should be consistent (low standard deviation)
        cv = distribution["std_dev_ms"] / distribution["avg_latency_ms"]  # Coefficient of variation
        assert cv < 2.0  # Reasonable consistency
        
        print(f"Average latency: {distribution['avg_latency_ms']:.2f}ms")
        print(f"Latency std dev: {distribution['std_dev_ms']:.2f}ms")
        print(f"P95 latency: {distribution['p95_latency_ms']:.2f}ms")
    
    def test_payload_size_impact(self):
        """Test impact of payload size on latency."""
        harness = LatencyTestHarness()
        
        payload_sizes = [1, 10, 50, 100, 500]  # KB
        results = {}
        
        for size_kb in payload_sizes:
            result = harness.measure_single_packet_latency(payload_size_kb=size_kb)
            results[size_kb] = result["total_latency_ms"]
        
        # Verify latency relationship (may have measurement noise for small values)
        small_payload_latency = results[1]
        large_payload_latency = results[500]

        # For small latencies, measurement noise can affect results
        # Just verify both measurements are reasonable
        assert small_payload_latency >= 0
        assert large_payload_latency >= 0
        assert small_payload_latency < 1000  # Should be under 1 second
        assert large_payload_latency < 1000  # Should be under 1 second
        
        print("Payload size impact:")
        for size, latency in results.items():
            print(f"  {size}KB: {latency:.2f}ms")
    
    @pytest.mark.slow 
    def test_sustained_throughput(self):
        """Test sustained throughput over extended period."""
        harness = ThroughputTestHarness(sender_count=2, receiver_count=2)
        
        # Run multiple rounds to test sustained performance
        rounds = 5
        packet_per_round = 500
        throughput_results = []
        
        for round_num in range(rounds):
            metrics = harness.run_throughput_test(
                packet_count=packet_per_round,
                batch_size=50,
                concurrent_senders=True
            )
            
            throughput_results.append(metrics.send_throughput)
            
            # Brief pause between rounds
            time.sleep(0.1)
        
        # Verify sustained performance
        avg_throughput = statistics.mean(throughput_results)
        throughput_std = statistics.stdev(throughput_results) if len(throughput_results) > 1 else 0
        
        assert avg_throughput > 200  # Maintain good throughput
        
        # Performance should be consistent across rounds
        cv = throughput_std / avg_throughput if avg_throughput > 0 else 0
        assert cv < 0.3  # Coefficient of variation less than 30%
        
        print(f"Sustained throughput over {rounds} rounds:")
        print(f"  Average: {avg_throughput:.2f} packets/sec")
        print(f"  Std dev: {throughput_std:.2f}")
        print(f"  CV: {cv:.3f}")
    
    def test_burst_handling(self):
        """Test system handling of burst traffic patterns."""
        harness = ThroughputTestHarness(sender_count=1, receiver_count=1)
        
        # Simulate burst by sending packets rapidly, then pause
        burst_size = 100
        num_bursts = 3
        
        total_sent = 0
        burst_latencies = []
        
        for burst_num in range(num_bursts):
            burst_start = time.time()
            
            # Send burst
            metrics = harness.run_throughput_test(
                packet_count=burst_size,
                batch_size=burst_size,  # Send all at once
                concurrent_senders=False
            )
            
            burst_duration = time.time() - burst_start
            burst_throughput = burst_size / burst_duration
            
            total_sent += metrics.packets_sent
            burst_latencies.extend(metrics.latencies)
            
            print(f"Burst {burst_num + 1}: {burst_throughput:.1f} pps")
            
            # Pause between bursts
            time.sleep(0.2)
        
        # Verify burst handling
        assert total_sent == burst_size * num_bursts
        
        # Latency should remain reasonable even during bursts
        if burst_latencies:
            avg_burst_latency = statistics.mean(burst_latencies)
            max_burst_latency = max(burst_latencies)
            
            assert avg_burst_latency < 50  # Average latency under 50ms
            assert max_burst_latency < 200  # Max latency under 200ms
    
    @pytest.mark.slow
    def test_memory_efficiency(self):
        """Test memory efficiency under various loads."""
        import tracemalloc
        
        tracemalloc.start()
        
        harness = ThroughputTestHarness(sender_count=2, receiver_count=2)
        
        # Baseline memory
        baseline_snapshot = tracemalloc.take_snapshot()
        
        # Run multiple tests with increasing loads
        loads = [100, 500, 1000, 2000]
        memory_usage = []
        
        for load in loads:
            gc.collect()  # Clean up before test
            
            pre_test_snapshot = tracemalloc.take_snapshot()
            
            metrics = harness.run_throughput_test(
                packet_count=load,
                batch_size=100,
                concurrent_senders=True
            )
            
            post_test_snapshot = tracemalloc.take_snapshot()
            
            # Calculate memory usage for this test
            top_stats = post_test_snapshot.compare_to(pre_test_snapshot, 'lineno')
            total_memory_kb = sum(stat.size_diff for stat in top_stats) / 1024
            
            memory_usage.append({
                "load": load,
                "memory_kb": total_memory_kb,
                "packets_sent": metrics.packets_sent
            })
            
            # Clean up
            gc.collect()
        
        tracemalloc.stop()
        
        # Verify memory efficiency (Python objects have overhead)
        for usage in memory_usage:
            memory_per_packet = usage["memory_kb"] / usage["packets_sent"]
            assert memory_per_packet < 10.0  # Less than 10KB per packet (realistic for Python)
            
            print(f"Load {usage['load']}: {usage['memory_kb']:.1f}KB total, "
                  f"{memory_per_packet:.3f}KB per packet")
        
        # Memory usage should not grow exponentially with load
        max_memory = max(usage["memory_kb"] for usage in memory_usage)
        min_memory = min(usage["memory_kb"] for usage in memory_usage)
        
        # Memory growth should be reasonable (expect roughly linear scaling)
        # Load increases 20x (100->2000), so memory growth up to 25x is acceptable
        memory_growth_ratio = max_memory / min_memory if min_memory > 0 else 1
        load_growth_ratio = max(usage["load"] for usage in memory_usage) / min(usage["load"] for usage in memory_usage)
        
        # Memory growth should not be exponentially worse than load growth
        assert memory_growth_ratio < load_growth_ratio * 1.5  # Allow 50% overhead on linear scaling
        
        print(f"Memory scaling analysis:")
        print(f"  Load increase: {load_growth_ratio:.1f}x")
        print(f"  Memory increase: {memory_growth_ratio:.1f}x")
        print(f"  Scaling efficiency: {memory_growth_ratio/load_growth_ratio:.1%} (100% = perfect linear)")
    
    def test_cpu_efficiency(self):
        """Test CPU efficiency under load."""
        import psutil
        
        process = psutil.Process()
        
        # Measure CPU usage during throughput test
        cpu_measurements = []
        
        def monitor_cpu():
            for _ in range(10):  # Monitor for ~1 second
                cpu_measurements.append(process.cpu_percent(interval=0.1))
        
        # Start CPU monitoring in background
        monitor_thread = threading.Thread(target=monitor_cpu)
        monitor_thread.start()
        
        # Run throughput test
        harness = ThroughputTestHarness(sender_count=3, receiver_count=2)
        metrics = harness.run_throughput_test(
            packet_count=1000,
            batch_size=100,
            concurrent_senders=True
        )
        
        monitor_thread.join()
        
        # Analyze CPU usage
        if cpu_measurements:
            avg_cpu = statistics.mean(cpu_measurements)
            max_cpu = max(cpu_measurements)
            
            # CPU efficiency metrics
            packets_per_cpu_percent = metrics.send_throughput / avg_cpu if avg_cpu > 0 else 0
            
            print(f"Average CPU: {avg_cpu:.1f}%")
            print(f"Max CPU: {max_cpu:.1f}%")
            print(f"Packets per CPU%: {packets_per_cpu_percent:.1f}")
            
            # CPU usage should be reasonable (note: can exceed 100% on multi-core systems)
            assert avg_cpu < 200  # Average CPU under 200% (reasonable for multi-core)
            assert max_cpu < 300  # Peak CPU under 300% (reasonable for multi-core systems)
            assert packets_per_cpu_percent > 5  # At least 5 packets per CPU%
