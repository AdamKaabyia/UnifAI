"""
Professional testing tools for comprehensive agent system testing.

This module provides reusable, professionally-designed test tools with proper
Pydantic schemas for use across all test suites. Tools are designed to simulate
real-world failure modes and edge cases.
"""

import time
import random
import json
import threading
from typing import Optional, Union, Any
from pydantic import BaseModel, Field
from mas.elements.tools.common.base_tool import BaseTool


# =============================================================================
# NETWORK SIMULATION TOOLS
# =============================================================================

class NetworkQueryInput(BaseModel):
    query: str = Field(..., description="Query to execute over network")
    
    
class ReliabilityTestInput(BaseModel):
    """Input schema for reliability testing tools."""
    operation: str = Field(default="test", description="Operation to perform")
    data: str = Field(default="", description="Data to process")


class UnreliableNetworkTool(BaseTool):
    """
    Tool that simulates network connectivity issues.
    
    Supports different connection states:
    - connected: Normal operation
    - disconnected: All requests fail
    - slow: Delayed responses with intermittent failures
    """
    
    name: str = "network_tool"
    description: str = "Tool that simulates network connectivity issues with realistic failure patterns"
    args_schema = NetworkQueryInput
    
    def __init__(self, name: str = "network_tool", connection_state: str = "connected"):
        self.name = name
        self.call_count = 0
        self.connection_state = connection_state  # connected, disconnected, slow
        
    def run(self, query: str, *args, **kwargs) -> str:
        self.call_count += 1
        
        if self.connection_state == "disconnected":
            raise ConnectionError(f"Network disconnected for {self.name}")
        elif self.connection_state == "slow":
            time.sleep(0.5)  # Simulate slow network
            if self.call_count % 3 == 0:  # Intermittent failures
                raise TimeoutError(f"Network timeout for {self.name}")
        
        return f"Network result for query: {query}"


# =============================================================================
# AUTHENTICATION & AUTHORIZATION TOOLS
# =============================================================================

class AuthOperationInput(BaseModel):
    action: str = Field(..., description="Action to perform (read/write/admin)")
    resource: str = Field(..., description="Resource to access")


class AuthenticationTool(BaseTool):
    """
    Tool that simulates authentication and authorization scenarios.
    
    Configurable permissions system allows testing of:
    - Permission escalation
    - Access control failures
    - Authentication requirements
    """
    
    name: str = "auth_tool"
    description: str = "Tool that simulates authentication and authorization with configurable permissions"
    args_schema = AuthOperationInput
    
    def __init__(self, name: str = "auth_tool", authenticated: bool = True, 
                 permissions: Optional[dict] = None):
        self.name = name
        self.authenticated = authenticated
        self.permissions = permissions or {"read": True, "write": False, "admin": False}
        
    def run(self, action: str, resource: str, *args, **kwargs) -> str:
        if not self.authenticated:
            raise PermissionError(f"Authentication required for {self.name}")
            
        if action not in self.permissions or not self.permissions[action]:
            raise PermissionError(f"Insufficient permissions for {action} on {resource}")
            
        return f"Auth success: {action} on {resource}"


# =============================================================================
# DATA PROCESSING & VALIDATION TOOLS
# =============================================================================

class DataProcessingInput(BaseModel):
    data: str = Field(..., description="Data to process")
    validate: bool = Field(default=True, description="Whether to validate data integrity")


class DataCorruptionTool(BaseTool):
    """
    Tool that simulates data corruption and validation errors.
    
    Configurable corruption rate allows testing of:
    - Data integrity validation
    - Corruption detection
    - Data size limits
    """
    
    name: str = "data_tool"
    description: str = "Tool that simulates data processing with configurable corruption rates"
    args_schema = DataProcessingInput
    
    def __init__(self, name: str = "data_tool", corruption_rate: float = 0.3):
        self.name = name
        self.corruption_rate = corruption_rate
        
    def run(self, data: str, validate: bool = True, *args, **kwargs) -> str:
        if validate and random.random() < self.corruption_rate:
            raise ValueError(f"Data corruption detected in {data}")
            
        # Simulate processing limits
        if len(data) > 100:
            raise ValueError("Data too large to process")
            
        return f"Processed data: {data[:50]}..."


# =============================================================================
# SERVICE RELIABILITY TOOLS
# =============================================================================

class ServiceOperationInput(BaseModel):
    operation: str = Field(..., description="Operation to perform on the service")


class CircuitBreakerTool(BaseTool):
    """
    Tool that simulates circuit breaker patterns.
    
    Simulates service failures followed by recovery, allowing testing of:
    - Circuit breaker behavior
    - Service degradation
    - Recovery patterns
    """
    
    name: str = "circuit_tool"
    description: str = "Tool that simulates circuit breaker patterns with configurable failure thresholds"
    args_schema = ServiceOperationInput
    
    def __init__(self, name: str = "circuit_tool", max_failures: int = 3):
        self.name = name
        self.failure_count = 0
        self.max_failures = max_failures
        
    def run(self, operation: str, *args, **kwargs) -> str:
        self.failure_count += 1
        
        if self.failure_count <= self.max_failures:
            raise RuntimeError(f"Service unavailable for {operation}")
        else:
            # After max failures, start succeeding
            return f"Circuit breaker recovered: {operation}"


# =============================================================================
# BOUNDARY TESTING TOOLS
# =============================================================================

class BoundaryTestInput(BaseModel):
    test_type: str = Field(..., description="Type of boundary test to perform")
    size: int = Field(default=0, description="Size parameter for the test")


class BoundaryTestTool(BaseTool):
    """
    Tool for testing system boundaries and limits.
    
    Supports various boundary conditions:
    - large_output: Generate outputs of specified size
    - unicode: Test unicode character handling
    - json: Test structured data handling
    - empty: Test empty response handling
    - null: Test null response handling
    """
    
    name: str = "boundary_tool"
    description: str = "Tool for comprehensive boundary condition testing"
    args_schema = BoundaryTestInput
    
    def __init__(self, name: str = "boundary_tool"):
        self.name = name
        
    def run(self, test_type: str, size: int = 0, *args, **kwargs) -> Union[str, None]:
        if test_type == "large_output":
            return "x" * size  # Generate large output
        elif test_type == "unicode":
            return "🚀🔥💯🎯✨🌟⭐🎉🎊🎈" * (size // 10)  # Unicode output
        elif test_type == "json":
            import json
            return json.dumps({"data": list(range(size))})  # Structured output
        elif test_type == "empty":
            return ""
        elif test_type == "null":
            return None
        else:
            return f"Normal output for {test_type}"


# =============================================================================
# PERFORMANCE TESTING TOOLS
# =============================================================================

class DelayOperationInput(BaseModel):
    delay: float = Field(default=0.1, description="Delay in seconds before completing operation")


class SlowTool(BaseTool):
    """
    Tool with configurable execution delays.
    
    Useful for testing:
    - Timeout handling
    - Concurrent execution
    - Performance under load
    """
    
    name: str = "slow_tool"
    description: str = "Tool with configurable execution delays for performance testing"
    args_schema = DelayOperationInput
    
    def __init__(self, name: str = "slow_tool"):
        self.name = name
        
    def run(self, delay: float = 0.1, *args, **kwargs) -> str:
        time.sleep(delay)
        return f"Completed after {delay}s delay"


class MemoryOperationInput(BaseModel):
    size_mb: int = Field(default=1, description="Memory allocation size in MB")


class MemoryIntensiveTool(BaseTool):
    """
    Tool that simulates memory-intensive operations.
    
    Useful for testing:
    - Memory pressure handling
    - Resource management
    - System limits
    """
    
    name: str = "memory_tool"
    description: str = "Tool that performs memory-intensive operations for resource testing"
    args_schema = MemoryOperationInput
    
    def __init__(self, name: str = "memory_tool"):
        self.name = name
        
    def run(self, size_mb: int = 1, *args, **kwargs) -> str:
        # Allocate memory (size in MB)
        data = bytearray(size_mb * 1024 * 1024)
        return f"Allocated {size_mb}MB of memory"


# =============================================================================
# RELIABILITY TESTING TOOLS
# =============================================================================

class ReliabilityTestTool(BaseTool):
    """
    Professional tool for testing reliability patterns with configurable failure rates.
    
    Combines features from FlakySLowTool with proper professional design:
    - Configurable failure rates (0.0-1.0)
    - Mixed error types (TimeoutError, ConnectionError, RuntimeError)
    - Execution delays
    - Call tracking
    """
    
    name: str = "reliability_tool"
    description: str = "Tool for testing reliability patterns with configurable failure rates and delays"
    args_schema = ReliabilityTestInput
    
    def __init__(self, name: str = "reliability_tool", failure_rate: float = 0.3, delay: float = 0.1):
        self.name = name
        self.failure_rate = max(0.0, min(1.0, failure_rate))  # Clamp to [0.0, 1.0]
        self.delay = delay
        self.call_count = 0
        self.success_count = 0
        self.failure_count = 0
        
    def run(self, operation: str = "test", data: str = "", *args, **kwargs) -> str:
        self.call_count += 1
        
        # Simulate execution delay
        if self.delay > 0:
            time.sleep(self.delay)
        
        # Simulate probabilistic failures
        if random.random() < self.failure_rate:
            self.failure_count += 1
            error_type = random.choice([
                (TimeoutError, f"Tool {self.name} timed out"),
                (ConnectionError, f"Tool {self.name} connection failed"),
                (RuntimeError, f"Tool {self.name} internal error")
            ])
            raise error_type[0](error_type[1])
        
        self.success_count += 1
        return f"Success from {self.name} (call #{self.call_count}): {operation} with data '{data}'"
    
    def get_stats(self) -> dict:
        """Get execution statistics."""
        return {
            "total_calls": self.call_count,
            "successes": self.success_count,
            "failures": self.failure_count,
            "success_rate": self.success_count / max(1, self.call_count),
            "failure_rate": self.failure_count / max(1, self.call_count)
        }
    
    def reset_stats(self):
        """Reset call statistics."""
        self.call_count = 0
        self.success_count = 0
        self.failure_count = 0


# =============================================================================
# FACTORY FUNCTIONS FOR COMMON TEST SCENARIOS
# =============================================================================

def create_flaky_tools(failure_rates: Optional[dict] = None) -> list[BaseTool]:
    """
    Create a set of tools with realistic failure patterns.
    
    Args:
        failure_rates: Custom failure rates for tools
        
    Returns:
        List of tools with configured failure behaviors
    """
    rates = failure_rates or {
        "network": 0.7,
        "auth": {"read": True, "write": False, "admin": False},
        "data": 0.3,
        "service": 3  # max failures before recovery
    }
    
    return [
        UnreliableNetworkTool("network_api", "slow"),
        AuthenticationTool("secure_service", True, rates["auth"]),
        DataCorruptionTool("data_processor", rates["data"]),
        CircuitBreakerTool("external_service", rates["service"]),
        ReliabilityTestTool("network_tool", rates["network"], 0.05),
        ReliabilityTestTool("api_tool", 0.6, 0.1),
        ReliabilityTestTool("memory_tool", 0.2, 0.02)
    ]


def create_boundary_test_tools() -> list[BaseTool]:
    """
    Create tools for boundary condition testing.
    
    Returns:
        List of tools for testing system limits and edge cases
    """
    return [
        BoundaryTestTool("boundary_test"),
        SlowTool("slow_processor"),
        MemoryIntensiveTool("memory_allocator")
    ]


def create_performance_test_tools() -> list[BaseTool]:
    """
    Create tools for performance and load testing.
    
    Returns:
        List of tools optimized for performance testing scenarios
    """
    return [
        SlowTool("perf_tool_1"),
        SlowTool("perf_tool_2"),
        MemoryIntensiveTool("memory_stress"),
        BoundaryTestTool("load_generator")
    ]


def create_load_testing_tools() -> list[BaseTool]:
    """
    Create tools specifically for load testing - reliable tools with predictable performance.
    
    These tools are designed to:
    - Execute successfully under normal conditions (high success rate)
    - Have predictable execution times
    - Scale well under concurrent load
    - Represent realistic workload patterns
    
    Returns:
        List of reliable tools for load testing scenarios
    """
    return [
        # CPU-bound tasks with predictable timing
        ReliabilityTestTool("cpu_task", failure_rate=0.05, delay=0.02),        # 95% success rate, fast
        ReliabilityTestTool("io_task", failure_rate=0.1, delay=0.05),          # 90% success rate, medium
        ReliabilityTestTool("network_task", failure_rate=0.15, delay=0.03),    # 85% success rate, fast
        
        # Memory operations
        ReliabilityTestTool("data_processing", failure_rate=0.08, delay=0.04), # 92% success rate
        ReliabilityTestTool("cache_operation", failure_rate=0.03, delay=0.01), # 97% success rate, very fast
        
        # Realistic service calls
        ReliabilityTestTool("api_service", failure_rate=0.12, delay=0.06),     # 88% success rate
        ReliabilityTestTool("database_query", failure_rate=0.07, delay=0.03),  # 93% success rate
        ReliabilityTestTool("file_operation", failure_rate=0.05, delay=0.02),  # 95% success rate
        
        # Different workload patterns
        ReliabilityTestTool("light_compute", failure_rate=0.02, delay=0.01),   # 98% success rate, very fast
        ReliabilityTestTool("heavy_compute", failure_rate=0.1, delay=0.08),    # 90% success rate, slower
    ]


# =============================================================================
# STRESS TESTING TOOLS - FOR EXTREME CONDITIONS
# =============================================================================

class StressTestInput(BaseModel):
    operation: str = Field(default="stress", description="Type of stress operation to perform")
    intensity: int = Field(default=1, description="Intensity level (1-10)")
    use_lock: bool = Field(default=False, description="Whether to use thread safety locks")

class ThreadSafetyTestTool(BaseTool):
    """
    Professional tool for testing thread safety and race conditions.
    
    Simulates thread-unsafe operations to test concurrency handling.
    """
    
    name: str = "thread_safety_tool"
    description: str = "Tool for testing thread safety and race conditions with configurable locks"
    args_schema = StressTestInput
    
    def __init__(self, name: str = "thread_safety_tool"):
        self.name = name
        self.shared_counter = 0
        self.shared_data = {}
        self.lock = threading.Lock()
        
    def run(self, operation: str = "increment", intensity: int = 1, use_lock: bool = False, *args, **kwargs) -> str:
        if use_lock:
            with self.lock:
                return self._unsafe_operation(operation, intensity)
        else:
            return self._unsafe_operation(operation, intensity)
    
    def _unsafe_operation(self, operation: str, intensity: int):
        if operation == "increment":
            for _ in range(intensity):
                old_value = self.shared_counter
                time.sleep(0.001)  # Race condition window
                self.shared_counter = old_value + 1
            return f"Counter: {self.shared_counter}"
        elif operation == "stress_data":
            for i in range(intensity):
                key = f"stress_{i}"
                self.shared_data[key] = f"value_{i}"
                time.sleep(0.001)
            return f"Stressed data: {len(self.shared_data)} items"
        else:
            return f"Stress operation: {operation} with intensity {intensity}"


class VariableDelayTestTool(BaseTool):
    """
    Professional tool for testing timeout and delay scenarios.
    """
    
    name: str = "variable_delay_tool"
    description: str = "Tool with configurable delays for timeout testing"
    args_schema = StressTestInput
    
    def __init__(self, name: str = "variable_delay_tool", max_delay: float = 2.0):
        self.name = name
        self.max_delay = max_delay
        
    def run(self, operation: str = "delay", intensity: int = 1, *args, **kwargs) -> str:
        # Scale delay based on intensity
        delay = min(self.max_delay, intensity * 0.1)
        
        if operation == "timeout_test":
            time.sleep(delay)
            return f"Completed after {delay}s delay"
        elif operation == "random_delay":
            random_delay = random.uniform(0, delay)
            time.sleep(random_delay)
            return f"Random delay: {random_delay:.3f}s"
        else:
            time.sleep(delay)
            return f"Variable delay operation: {operation}"


class ParserStressTool(BaseTool):
    """
    Professional tool for generating parser stress responses.
    """
    
    name: str = "parser_stress_tool"
    description: str = "Tool that generates various response formats for parser stress testing"
    args_schema = StressTestInput
    
    def __init__(self, name: str = "parser_stress_tool"):
        self.name = name
        
    def run(self, operation: str = "normal", intensity: int = 1, *args, **kwargs) -> str:
        if operation == "large_response":
            size = min(50000, intensity * 1000)  # Up to 50KB
            return "X" * size
        elif operation == "unicode_stress":
            unicode_chars = "🚀🔥💯🎉🌟⚡️🎯🔧🧪📊"
            return unicode_chars * (intensity * 10)
        elif operation == "json_response":
            depth = min(10, intensity)
            nested = {"level": 0}
            current = nested
            for i in range(1, depth):
                current["nested"] = {"level": i}
                current = current["nested"]
            return json.dumps(nested)
        elif operation == "xml_response":
            content = "<root>"
            for i in range(intensity):
                content += f"<item{i}>data{i}</item{i}>"
            content += "</root>"
            return content
        else:
            return f"Parser stress response: {operation} (intensity: {intensity})"


def create_stress_testing_tools() -> list[BaseTool]:
    """
    Create professional tools for stress testing extreme conditions.
    
    These tools are designed for:
    - Thread safety testing
    - Race condition simulation
    - Timeout and delay scenarios
    - Parser stress testing
    - Memory pressure scenarios
    
    Returns:
        List of tools for stress testing scenarios
    """
    return [
        ThreadSafetyTestTool("thread_safety_tool"),
        ThreadSafetyTestTool("race_condition_tool"),
        VariableDelayTestTool("timeout_test_tool", max_delay=1.0),
        VariableDelayTestTool("slow_response_tool", max_delay=2.0),
        ParserStressTool("parser_stress_tool"),
        ParserStressTool("response_generator_tool"),
        ReliabilityTestTool("memory_pressure_tool", failure_rate=0.2, delay=0.05),
        ReliabilityTestTool("resource_intensive_tool", failure_rate=0.15, delay=0.1),
    ]
