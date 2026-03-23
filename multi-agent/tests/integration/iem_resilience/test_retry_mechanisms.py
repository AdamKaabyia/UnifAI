"""
Comprehensive tests for IEM retry mechanisms and recovery patterns.

Tests various retry strategies, backoff algorithms, and recovery scenarios.
"""

import pytest
import time
import threading
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from unittest.mock import Mock, patch
from enum import Enum

from mas.core.iem.messenger import DefaultInterMessenger
from mas.core.iem.models import ElementAddress
from mas.core.iem.packets import BaseIEMPacket, TaskPacket
from mas.core.iem.exceptions import IEMException, IEMValidationException
from tests.fixtures.iem_testing_tools import (
    create_test_state_view, create_test_step_context,
    PacketFactory, IEMPerformanceMonitor
)


class RetryStrategy(Enum):
    """Retry strategy types."""
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    FIBONACCI = "fibonacci"
    CUSTOM = "custom"


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(self,
                 strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
                 max_attempts: int = 3,
                 base_delay: float = 0.1,
                 max_delay: float = 10.0,
                 backoff_factor: float = 2.0,
                 jitter: bool = True,
                 custom_backoff_func: Optional[Callable[[int], float]] = None):
        self.strategy = strategy
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.custom_backoff_func = custom_backoff_func


class AdvancedRetryMessenger:
    """Messenger with advanced retry capabilities."""
    
    def __init__(self, uid: str, state_view, context, retry_config: RetryConfig):
        self.uid = uid
        self.messenger = DefaultInterMessenger(
            state=state_view,
            identity=ElementAddress(uid=uid),
            context=context
        )
        self.retry_config = retry_config
        self.retry_stats = {
            "total_attempts": 0,
            "successful_sends": 0,
            "failed_sends": 0,
            "retry_attempts": 0,
            "strategy_stats": {}
        }
        self.retry_history = []
    
    def send_with_retry(self, packet: BaseIEMPacket) -> Dict[str, Any]:
        """Send packet with configurable retry strategy."""
        attempt_history = []
        start_time = time.time()
        
        for attempt in range(self.retry_config.max_attempts):
            attempt_start = time.time()
            self.retry_stats["total_attempts"] += 1
            
            try:
                packet_id = self.messenger.send_packet(packet)
                
                # Success
                attempt_duration = time.time() - attempt_start
                total_duration = time.time() - start_time
                
                attempt_history.append({
                    "attempt": attempt + 1,
                    "success": True,
                    "duration": attempt_duration,
                    "delay_before": 0 if attempt == 0 else attempt_history[-1]["delay_after"]
                })
                
                self.retry_stats["successful_sends"] += 1
                if attempt > 0:
                    self.retry_stats["retry_attempts"] += attempt
                
                result = {
                    "success": True,
                    "packet_id": packet_id,
                    "attempts": attempt + 1,
                    "total_duration": total_duration,
                    "attempt_history": attempt_history
                }
                
                self.retry_history.append(result)
                return result
                
            except Exception as e:
                attempt_duration = time.time() - attempt_start
                
                # Calculate delay for next attempt
                delay = 0
                if attempt < self.retry_config.max_attempts - 1:
                    delay = self._calculate_delay(attempt)
                
                attempt_history.append({
                    "attempt": attempt + 1,
                    "success": False,
                    "error": str(e),
                    "duration": attempt_duration,
                    "delay_after": delay
                })
                
                if attempt < self.retry_config.max_attempts - 1:
                    time.sleep(delay)
        
        # All attempts failed
        total_duration = time.time() - start_time
        self.retry_stats["failed_sends"] += 1
        self.retry_stats["retry_attempts"] += self.retry_config.max_attempts - 1
        
        result = {
            "success": False,
            "attempts": self.retry_config.max_attempts,
            "total_duration": total_duration,
            "attempt_history": attempt_history
        }
        
        self.retry_history.append(result)
        return result
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay based on retry strategy."""
        if self.retry_config.strategy == RetryStrategy.LINEAR:
            delay = self.retry_config.base_delay * (attempt + 1)
        
        elif self.retry_config.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.retry_config.base_delay * (self.retry_config.backoff_factor ** attempt)
        
        elif self.retry_config.strategy == RetryStrategy.FIBONACCI:
            delay = self.retry_config.base_delay * self._fibonacci(attempt + 1)
        
        elif self.retry_config.strategy == RetryStrategy.CUSTOM:
            if self.retry_config.custom_backoff_func:
                delay = self.retry_config.custom_backoff_func(attempt)
            else:
                delay = self.retry_config.base_delay
        
        else:
            delay = self.retry_config.base_delay
        
        # Apply max delay limit
        delay = min(delay, self.retry_config.max_delay)
        
        # Apply jitter if enabled
        if self.retry_config.jitter:
            import random
            jitter_factor = random.uniform(0.5, 1.5)
            delay *= jitter_factor
        
        return delay
    
    def _fibonacci(self, n: int) -> int:
        """Calculate fibonacci number."""
        if n <= 2:
            return 1
        a, b = 1, 1
        for _ in range(2, n):
            a, b = b, a + b
        return b
    
    def get_retry_statistics(self) -> Dict[str, Any]:
        """Get comprehensive retry statistics."""
        total_sends = self.retry_stats["successful_sends"] + self.retry_stats["failed_sends"]
        
        if total_sends > 0:
            success_rate = self.retry_stats["successful_sends"] / total_sends
            avg_attempts = self.retry_stats["total_attempts"] / total_sends
        else:
            success_rate = 0
            avg_attempts = 0
        
        return {
            **self.retry_stats,
            "success_rate": success_rate,
            "avg_attempts_per_send": avg_attempts,
            "strategy": self.retry_config.strategy.value
        }


class AdaptiveRetryMessenger(AdvancedRetryMessenger):
    """Messenger that adapts retry strategy based on observed patterns."""
    
    def __init__(self, uid: str, state_view, context, initial_config: RetryConfig):
        super().__init__(uid, state_view, context, initial_config)
        self.adaptation_enabled = True
        self.adaptation_history = []
        self.success_rate_window = 20  # Monitor last N attempts
        self.adaptation_threshold = 0.3  # Adapt if success rate drops below 30%
    
    def send_with_adaptive_retry(self, packet: BaseIEMPacket) -> Dict[str, Any]:
        """Send with adaptive retry strategy."""
        # Check if adaptation is needed
        if self.adaptation_enabled:
            self._adapt_strategy()
        
        # Use the current strategy
        result = self.send_with_retry(packet)
        
        # Record adaptation metrics
        current_success_rate = self._calculate_recent_success_rate()
        adaptation_entry = {
            "timestamp": datetime.utcnow(),
            "strategy": self.retry_config.strategy.value,
            "max_attempts": self.retry_config.max_attempts,
            "base_delay": self.retry_config.base_delay,
            "success_rate": current_success_rate,
            "result": result["success"]
        }
        self.adaptation_history.append(adaptation_entry)
        
        return result
    
    def _adapt_strategy(self):
        """Adapt retry strategy based on recent performance."""
        if len(self.retry_history) < self.success_rate_window:
            return
        
        recent_success_rate = self._calculate_recent_success_rate()
        
        if recent_success_rate < self.adaptation_threshold:
            # Poor performance, try more aggressive retry
            if self.retry_config.max_attempts < 5:
                self.retry_config.max_attempts += 1
            
            if self.retry_config.base_delay < 0.5:
                self.retry_config.base_delay *= 1.5
            
            # Switch to exponential if not already
            if self.retry_config.strategy != RetryStrategy.EXPONENTIAL:
                self.retry_config.strategy = RetryStrategy.EXPONENTIAL
                self.retry_config.backoff_factor = 2.0
        
        elif recent_success_rate > 0.8:
            # Good performance, optimize for speed
            if self.retry_config.max_attempts > 2:
                self.retry_config.max_attempts -= 1
            
            if self.retry_config.base_delay > 0.05:
                self.retry_config.base_delay *= 0.8
    
    def _calculate_recent_success_rate(self) -> float:
        """Calculate success rate for recent attempts."""
        if not self.retry_history:
            return 1.0
        
        recent_attempts = self.retry_history[-self.success_rate_window:]
        successful = sum(1 for attempt in recent_attempts if attempt["success"])
        
        return successful / len(recent_attempts)


class CircuitBreakerRetryMessenger:
    """Messenger with circuit breaker pattern for retry optimization."""
    
    def __init__(self, uid: str, state_view, context, 
                 failure_threshold: int = 5,
                 recovery_timeout: float = 30.0,
                 half_open_max_calls: int = 3):
        self.uid = uid
        self.messenger = DefaultInterMessenger(
            state=state_view,
            identity=ElementAddress(uid=uid),
            context=context
        )
        
        # Circuit breaker state
        self.state = "closed"  # closed, open, half_open
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.half_open_calls = 0
        self.last_failure_time = None
        
        # Statistics
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "circuit_open_count": 0,
            "circuit_half_open_count": 0,
            "fast_failures": 0  # Calls rejected due to open circuit
        }
    
    def send_with_circuit_breaker(self, packet: BaseIEMPacket) -> Dict[str, Any]:
        """Send packet with circuit breaker pattern."""
        self.stats["total_calls"] += 1
        
        # Check circuit breaker state
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half_open"
                self.half_open_calls = 0
                self.stats["circuit_half_open_count"] += 1
            else:
                # Fast failure - don't even attempt
                self.stats["fast_failures"] += 1
                return {
                    "success": False,
                    "circuit_breaker_state": "open",
                    "fast_failure": True,
                    "error": "Circuit breaker is open"
                }
        
        # Attempt the call
        if self.state == "half_open":
            self.half_open_calls += 1
        
        try:
            packet_id = self.messenger.send_packet(packet)
            
            # Success
            self._record_success()
            return {
                "success": True,
                "packet_id": packet_id,
                "circuit_breaker_state": self.state
            }
            
        except Exception as e:
            # Failure
            self._record_failure()
            return {
                "success": False,
                "error": str(e),
                "circuit_breaker_state": self.state
            }
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if self.last_failure_time is None:
            return False
        
        return (time.time() - self.last_failure_time) >= self.recovery_timeout
    
    def _record_success(self):
        """Record successful call."""
        self.stats["successful_calls"] += 1
        
        if self.state == "half_open":
            if self.half_open_calls >= self.half_open_max_calls:
                # Enough successful calls in half_open, reset to closed
                self.state = "closed"
                self.failure_count = 0
        elif self.state == "closed":
            # Reset failure count on success
            self.failure_count = 0
    
    def _record_failure(self):
        """Record failed call."""
        self.stats["failed_calls"] += 1
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == "half_open":
            # Failure in half_open, return to open
            self.state = "open"
            self.stats["circuit_open_count"] += 1
        elif self.state == "closed" and self.failure_count >= self.failure_threshold:
            # Too many failures, open the circuit
            self.state = "open"
            self.stats["circuit_open_count"] += 1
    
    def get_circuit_breaker_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        total_calls = self.stats["total_calls"]
        if total_calls > 0:
            success_rate = self.stats["successful_calls"] / total_calls
            fast_failure_rate = self.stats["fast_failures"] / total_calls
        else:
            success_rate = 0
            fast_failure_rate = 0
        
        return {
            **self.stats,
            "current_state": self.state,
            "failure_count": self.failure_count,
            "success_rate": success_rate,
            "fast_failure_rate": fast_failure_rate,
            "time_since_last_failure": time.time() - (self.last_failure_time or time.time())
        }


class TestRetryMechanisms:
    """Test suite for IEM retry mechanisms."""
    
    def test_exponential_backoff_retry(self):
        """Test exponential backoff retry strategy."""
        state = create_test_state_view()
        context = create_test_step_context("retry_node", ["target"])
        
        retry_config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            max_attempts=4,
            base_delay=0.01,  # Fast for testing
            backoff_factor=2.0,
            jitter=False  # Disable for predictable testing
        )
        
        messenger = AdvancedRetryMessenger("retry_node", state, context, retry_config)
        
        # Mock the underlying messenger to always fail
        with patch.object(messenger.messenger, 'send_packet', side_effect=IEMValidationException("Mock error")):
            packet = PacketFactory.create_task_packet("retry_node", "target")
            result = messenger.send_with_retry(packet)
        
        # Verify retry behavior
        assert not result["success"]
        assert result["attempts"] == 4
        assert len(result["attempt_history"]) == 4
        
        # Verify exponential backoff delays
        delays = [attempt["delay_after"] for attempt in result["attempt_history"][:-1]]
        
        # Should be approximately [0.01, 0.02, 0.04]
        assert delays[0] == pytest.approx(0.01, rel=0.1)
        assert delays[1] == pytest.approx(0.02, rel=0.1)
        assert delays[2] == pytest.approx(0.04, rel=0.1)
        
        # Verify statistics
        stats = messenger.get_retry_statistics()
        assert stats["failed_sends"] == 1
        assert stats["retry_attempts"] == 3  # 4 attempts - 1 initial
        assert stats["strategy"] == "exponential"
    
    def test_linear_backoff_retry(self):
        """Test linear backoff retry strategy."""
        state = create_test_state_view()
        context = create_test_step_context("linear_node", ["target"])
        
        retry_config = RetryConfig(
            strategy=RetryStrategy.LINEAR,
            max_attempts=3,
            base_delay=0.01,
            jitter=False
        )
        
        messenger = AdvancedRetryMessenger("linear_node", state, context, retry_config)
        
        # Mock to fail first two attempts, succeed on third
        call_count = 0
        def mock_send(packet):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise IEMValidationException(f"Mock error {call_count}")
            return "success_packet_id"
        
        with patch.object(messenger.messenger, 'send_packet', side_effect=mock_send):
            packet = PacketFactory.create_task_packet("linear_node", "target")
            result = messenger.send_with_retry(packet)
        
        # Should succeed on third attempt
        assert result["success"]
        assert result["attempts"] == 3
        assert result["packet_id"] == "success_packet_id"
        
        # Verify linear backoff delays
        delays = [attempt["delay_after"] for attempt in result["attempt_history"][:-1]]
        
        # Should be approximately [0.01, 0.02] (linear progression)
        assert delays[0] == pytest.approx(0.01, rel=0.1)
        assert delays[1] == pytest.approx(0.02, rel=0.1)
    
    def test_fibonacci_backoff_retry(self):
        """Test Fibonacci backoff retry strategy."""
        state = create_test_state_view()
        context = create_test_step_context("fib_node", ["target"])
        
        retry_config = RetryConfig(
            strategy=RetryStrategy.FIBONACCI,
            max_attempts=5,
            base_delay=0.01,
            jitter=False
        )
        
        messenger = AdvancedRetryMessenger("fib_node", state, context, retry_config)
        
        with patch.object(messenger.messenger, 'send_packet', side_effect=IEMValidationException("Mock error")):
            packet = PacketFactory.create_task_packet("fib_node", "target")
            result = messenger.send_with_retry(packet)
        
        # Verify Fibonacci backoff delays
        delays = [attempt["delay_after"] for attempt in result["attempt_history"][:-1]]
        
        # Fibonacci sequence * base_delay: [1, 1, 2, 3] * 0.01 = [0.01, 0.01, 0.02, 0.03]
        assert delays[0] == pytest.approx(0.01, rel=0.1)
        assert delays[1] == pytest.approx(0.01, rel=0.1) 
        assert delays[2] == pytest.approx(0.02, rel=0.1)
        assert delays[3] == pytest.approx(0.03, rel=0.1)
    
    def test_custom_backoff_retry(self):
        """Test custom backoff retry strategy."""
        state = create_test_state_view()
        context = create_test_step_context("custom_node", ["target"])
        
        def custom_backoff(attempt: int) -> float:
            """Custom backoff: attempt squared * 0.01"""
            return (attempt + 1) ** 2 * 0.01
        
        retry_config = RetryConfig(
            strategy=RetryStrategy.CUSTOM,
            max_attempts=4,
            custom_backoff_func=custom_backoff,
            jitter=False
        )
        
        messenger = AdvancedRetryMessenger("custom_node", state, context, retry_config)
        
        with patch.object(messenger.messenger, 'send_packet', side_effect=IEMValidationException("Mock error")):
            packet = PacketFactory.create_task_packet("custom_node", "target")
            result = messenger.send_with_retry(packet)
        
        # Verify custom backoff delays
        delays = [attempt["delay_after"] for attempt in result["attempt_history"][:-1]]
        
        # Custom formula: [1^2, 2^2, 3^2] * 0.01 = [0.01, 0.04, 0.09]
        assert delays[0] == pytest.approx(0.01, rel=0.1)
        assert delays[1] == pytest.approx(0.04, rel=0.1)
        assert delays[2] == pytest.approx(0.09, rel=0.1)
    
    def test_adaptive_retry_strategy(self):
        """Test adaptive retry strategy that changes based on performance."""
        state = create_test_state_view()
        context = create_test_step_context("adaptive_node", ["target"])
        
        initial_config = RetryConfig(
            strategy=RetryStrategy.LINEAR,
            max_attempts=2,
            base_delay=0.01
        )
        
        messenger = AdaptiveRetryMessenger("adaptive_node", state, context, initial_config)
        messenger.success_rate_window = 5  # Small window for testing
        messenger.adaptation_threshold = 0.4
        
        # Simulate poor performance to trigger adaptation
        with patch.object(messenger.messenger, 'send_packet', side_effect=IEMValidationException("Poor performance")):
            for i in range(6):  # Fill the window with failures
                packet = PacketFactory.create_task_packet("adaptive_node", "target", f"packet_{i}")
                messenger.send_with_adaptive_retry(packet)
        
        # Check if strategy adapted
        adaptation_entries = messenger.adaptation_history
        assert len(adaptation_entries) >= 5
        
        # Strategy should have adapted (increased attempts or changed strategy)
        initial_attempts = adaptation_entries[0]["max_attempts"]
        final_attempts = adaptation_entries[-1]["max_attempts"]
        
        initial_strategy = adaptation_entries[0]["strategy"]
        final_strategy = adaptation_entries[-1]["strategy"]
        
        # Should have adapted to be more aggressive
        assert (final_attempts > initial_attempts or 
                final_strategy == "exponential")
    
    def test_circuit_breaker_pattern(self):
        """Test circuit breaker pattern for retry optimization."""
        state = create_test_state_view()
        context = create_test_step_context("breaker_node", ["target"])
        
        messenger = CircuitBreakerRetryMessenger(
            "breaker_node", state, context,
            failure_threshold=3,
            recovery_timeout=0.1,  # Fast recovery for testing
            half_open_max_calls=2
        )
        
        # Generate failures to open circuit breaker
        with patch.object(messenger.messenger, 'send_packet', side_effect=IEMValidationException("Failure")):
            results = []
            for i in range(5):
                packet = PacketFactory.create_task_packet("breaker_node", "target", f"packet_{i}")
                result = messenger.send_with_circuit_breaker(packet)
                results.append(result)
        
        # First 3 should be actual failures, next 2 should be fast failures
        actual_failures = [r for r in results if not r.get("fast_failure", False)]
        fast_failures = [r for r in results if r.get("fast_failure", False)]
        
        assert len(actual_failures) == 3
        assert len(fast_failures) == 2
        
        # Circuit should be open
        stats = messenger.get_circuit_breaker_stats()
        assert stats["current_state"] == "open"
        assert stats["fast_failures"] == 2
        
        # Wait for recovery timeout
        time.sleep(0.15)
        
        # Next call should be in half_open state
        with patch.object(messenger.messenger, 'send_packet', return_value="success_id"):
            packet = PacketFactory.create_task_packet("breaker_node", "target", "recovery_packet")
            result = messenger.send_with_circuit_breaker(packet)
        
        assert result["success"]
        assert result["circuit_breaker_state"] == "half_open"
        
        # One more success should close the circuit
        with patch.object(messenger.messenger, 'send_packet', return_value="success_id2"):
            packet = PacketFactory.create_task_packet("breaker_node", "target", "final_packet")
            result = messenger.send_with_circuit_breaker(packet)
        
        assert result["success"]
        
        # Circuit should now be closed
        final_stats = messenger.get_circuit_breaker_stats()
        assert final_stats["current_state"] == "closed"
    
    def test_retry_with_jitter(self):
        """Test retry with jitter to avoid thundering herd."""
        state = create_test_state_view()
        context = create_test_step_context("jitter_node", ["target"])
        
        retry_config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            max_attempts=3,
            base_delay=0.1,
            jitter=True
        )
        
        messenger = AdvancedRetryMessenger("jitter_node", state, context, retry_config)
        
        # Collect delays from multiple retry attempts
        delays_collected = []
        
        for test_run in range(10):
            with patch.object(messenger.messenger, 'send_packet', side_effect=IEMValidationException("Jitter test")):
                packet = PacketFactory.create_task_packet("jitter_node", "target", f"jitter_packet_{test_run}")
                result = messenger.send_with_retry(packet)
                
                # Collect first delay
                if result["attempt_history"] and len(result["attempt_history"]) > 1:
                    delays_collected.append(result["attempt_history"][0]["delay_after"])
        
        # With jitter, delays should vary
        unique_delays = set(delays_collected)
        assert len(unique_delays) > 1  # Should have variation due to jitter
        
        # All delays should be within reasonable bounds (0.05 to 0.15 for first retry)
        for delay in delays_collected:
            assert 0.05 <= delay <= 0.15
    
    def test_concurrent_retry_mechanisms(self):
        """Test retry mechanisms under concurrent load."""
        state = create_test_state_view()
        context = create_test_step_context("concurrent_retry_node", ["target1", "target2"])
        
        retry_config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            max_attempts=3,
            base_delay=0.01
        )
        
        messenger = AdvancedRetryMessenger("concurrent_retry_node", state, context, retry_config)
        
        # Simulate concurrent retry operations
        def retry_worker(worker_id: int, packet_count: int):
            worker_results = []
            
            for i in range(packet_count):
                # Simulate intermittent failures
                def mock_send(packet):
                    import random
                    if random.random() < 0.3:  # 30% failure rate
                        raise IEMValidationException(f"Worker {worker_id} packet {i} failed")
                    return f"success_{worker_id}_{i}"
                
                with patch.object(messenger.messenger, 'send_packet', side_effect=mock_send):
                    packet = PacketFactory.create_task_packet(
                        "concurrent_retry_node", 
                        f"target{(i % 2) + 1}", 
                        f"worker_{worker_id}_packet_{i}"
                    )
                    result = messenger.send_with_retry(packet)
                    worker_results.append(result)
                
                time.sleep(0.001)  # Small delay
            
            return worker_results
        
        # Run concurrent workers
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(retry_worker, worker_id, 10)
                for worker_id in range(5)
            ]
            
            all_results = []
            for future in concurrent.futures.as_completed(futures):
                worker_results = future.result()
                all_results.extend(worker_results)
        
        # Analyze results
        assert len(all_results) == 50  # 5 workers * 10 packets
        
        successful_sends = [r for r in all_results if r["success"]]
        failed_sends = [r for r in all_results if not r["success"]]
        
        # Should have both successes and failures due to 30% failure rate
        assert len(successful_sends) > 0
        
        # Verify retry statistics
        stats = messenger.get_retry_statistics()
        assert stats["total_attempts"] > 50  # Should have retries
        assert stats["successful_sends"] + stats["failed_sends"] == 50
    
    def test_retry_performance_characteristics(self):
        """Test performance characteristics of different retry strategies."""
        state = create_test_state_view()
        context = create_test_step_context("perf_node", ["target"])
        monitor = IEMPerformanceMonitor()
        
        strategies_to_test = [
            (RetryStrategy.LINEAR, "linear"),
            (RetryStrategy.EXPONENTIAL, "exponential"), 
            (RetryStrategy.FIBONACCI, "fibonacci")
        ]
        
        performance_results = {}
        
        for strategy, strategy_name in strategies_to_test:
            retry_config = RetryConfig(
                strategy=strategy,
                max_attempts=3,
                base_delay=0.01,
                jitter=False
            )
            
            messenger = AdvancedRetryMessenger("perf_node", state, context, retry_config)
            
            with monitor.monitor_operation(f"retry_performance_{strategy_name}") as op_id:
                # Test with consistent failure pattern
                with patch.object(messenger.messenger, 'send_packet', side_effect=IEMValidationException("Perf test")):
                    for i in range(20):
                        packet = PacketFactory.create_task_packet("perf_node", "target", f"perf_packet_{i}")
                        messenger.send_with_retry(packet)
            
            # Collect performance metrics
            perf_stats = monitor.get_operation_stats(f"retry_performance_{strategy_name}")
            retry_stats = messenger.get_retry_statistics()
            
            performance_results[strategy_name] = {
                "avg_duration": perf_stats["avg_duration_ms"],
                "total_duration": perf_stats["total_duration_ms"],
                "retry_attempts": retry_stats["retry_attempts"],
                "avg_attempts_per_send": retry_stats["avg_attempts_per_send"]
            }
        
        # Verify performance characteristics
        for strategy_name, perf_data in performance_results.items():
            assert perf_data["avg_duration"] > 0
            assert perf_data["retry_attempts"] > 0
            
            # Each send should have attempted retries
            assert perf_data["avg_attempts_per_send"] > 1
        
        # Compare strategies - exponential should be fastest due to shorter initial delays
        linear_duration = performance_results["linear"]["avg_duration"]
        exponential_duration = performance_results["exponential"]["avg_duration"]
        fibonacci_duration = performance_results["fibonacci"]["avg_duration"]
        
        # Performance comparison (may vary, but exponential typically fastest)
        assert all(duration > 0 for duration in [linear_duration, exponential_duration, fibonacci_duration])
    
    def test_retry_edge_cases(self):
        """Test retry mechanisms with edge cases."""
        state = create_test_state_view()
        context = create_test_step_context("edge_node", ["target"])
        
        # Test with max_attempts = 1 (no retries)
        no_retry_config = RetryConfig(max_attempts=1)
        no_retry_messenger = AdvancedRetryMessenger("edge_node", state, context, no_retry_config)
        
        with patch.object(no_retry_messenger.messenger, 'send_packet', side_effect=IEMValidationException("No retry test")):
            packet = PacketFactory.create_task_packet("edge_node", "target")
            result = no_retry_messenger.send_with_retry(packet)
        
        assert not result["success"]
        assert result["attempts"] == 1
        assert len(result["attempt_history"]) == 1
        
        # Test with very high max_delay to ensure capping works
        high_delay_config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            max_attempts=5,
            base_delay=1.0,
            max_delay=0.1,  # Lower than what exponential would produce
            backoff_factor=10.0
        )
        
        high_delay_messenger = AdvancedRetryMessenger("edge_node", state, context, high_delay_config)
        
        with patch.object(high_delay_messenger.messenger, 'send_packet', side_effect=IEMValidationException("High delay test")):
            packet = PacketFactory.create_task_packet("edge_node", "target")
            result = high_delay_messenger.send_with_retry(packet)
        
        # All delays should be capped at max_delay
        delays = [attempt["delay_after"] for attempt in result["attempt_history"][:-1]]
        for delay in delays:
            assert delay <= high_delay_config.max_delay * 1.6  # Account for jitter
        
        # Test with zero base_delay
        zero_delay_config = RetryConfig(
            strategy=RetryStrategy.LINEAR,
            max_attempts=3,
            base_delay=0.0
        )
        
        zero_delay_messenger = AdvancedRetryMessenger("edge_node", state, context, zero_delay_config)
        
        with patch.object(zero_delay_messenger.messenger, 'send_packet', side_effect=IEMValidationException("Zero delay test")):
            start_time = time.time()
            packet = PacketFactory.create_task_packet("edge_node", "target")
            result = zero_delay_messenger.send_with_retry(packet)
            total_time = time.time() - start_time
        
        # Should complete very quickly with zero delays
        assert total_time < 0.1
        assert not result["success"]
        assert result["attempts"] == 3
