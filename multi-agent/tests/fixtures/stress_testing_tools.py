"""
Stress testing tools for comprehensive system validation.

This module provides specialized tools for stress testing, concurrency testing,
and race condition detection with proper Pydantic schemas.
"""

import time
import threading
import random
from typing import Optional, Any
from pydantic import BaseModel, Field
from mas.elements.tools.common.base_tool import BaseTool


# =============================================================================
# CONCURRENCY & RACE CONDITION TESTING TOOLS
# =============================================================================

class RaceConditionInput(BaseModel):
    operation: str = Field(..., description="Operation to perform (increment/set/get)")
    key: Optional[str] = Field(None, description="Key for set/get operations")
    value: Optional[str] = Field(None, description="Value for set operations")
    use_lock: bool = Field(default=False, description="Whether to use thread synchronization")


class RacyTool(BaseTool):
    """
    Tool that simulates race conditions and thread safety issues.
    
    Useful for testing:
    - Concurrent access patterns
    - Thread safety
    - Race condition handling
    - Synchronization mechanisms
    """
    
    name: str = "racy_tool"
    description: str = "Tool that simulates race conditions and thread safety issues"
    args_schema = RaceConditionInput
    
    def __init__(self, name: str = "racy_tool"):
        self.name = name
        self.shared_counter = 0
        self.shared_data = {}
        self.lock = threading.Lock()
        
    def run(self, operation: str, key: Optional[str] = None, 
            value: Optional[str] = None, use_lock: bool = False, 
            *args, **kwargs) -> str:
        if use_lock:
            with self.lock:
                return self._unsafe_operation(operation, key, value)
        else:
            return self._unsafe_operation(operation, key, value)
    
    def _unsafe_operation(self, operation: str, key: Optional[str], value: Optional[str]) -> str:
        if operation == "increment":
            old_value = self.shared_counter
            time.sleep(0.001)  # Simulate race condition window
            self.shared_counter = old_value + 1
            return f"Counter: {self.shared_counter}"
        elif operation == "set" and key and value:
            self.shared_data[key] = value
            time.sleep(0.001)
            return f"Set {key}={value}"
        elif operation == "get" and key:
            time.sleep(0.001)
            return self.shared_data.get(key, "NOT_FOUND")
        else:
            return "Invalid operation"


# =============================================================================
# VARIABLE DELAY TESTING TOOLS
# =============================================================================

class VariableDelayInput(BaseModel):
    operation: str = Field(default="process", description="Operation to perform")
    custom_delay: Optional[float] = Field(None, description="Custom delay override")


class VariableDelayTool(BaseTool):
    """
    Tool with configurable delays for timeout and performance testing.
    
    More flexible than the basic SlowTool, supports:
    - Custom delays per operation
    - Random delay variations
    - Timeout simulation
    """
    
    name: str = "variable_delay_tool"
    description: str = "Tool with configurable delays for timeout testing"
    args_schema = VariableDelayInput
    
    def __init__(self, name: str = "variable_delay_tool", base_delay: float = 1.0):
        self.name = name
        self.base_delay = base_delay
        
    def run(self, operation: str = "process", custom_delay: Optional[float] = None, 
            *args, **kwargs) -> str:
        delay = custom_delay if custom_delay is not None else self.base_delay
        time.sleep(delay)
        return f"Completed {operation} after {delay}s delay"


# =============================================================================
# PARSER STRESS TESTING TOOLS
# =============================================================================

class RandomResponseInput(BaseModel):
    response_type: str = Field(default="random", description="Type of random response to generate")
    size: int = Field(default=100, description="Size parameter for response generation")


class RandomResponseTool(BaseTool):
    """
    Tool that returns random responses to stress test parsers.
    
    Generates various response types:
    - Random strings
    - Malformed JSON
    - Unicode chaos
    - Large responses
    - Empty responses
    """
    
    name: str = "random_response_tool"
    description: str = "Tool that generates random responses for parser stress testing"
    args_schema = RandomResponseInput
    
    def __init__(self, name: str = "random_response_tool"):
        self.name = name
        self.response_types = [
            "random_string", "malformed_json", "unicode_chaos", 
            "large_response", "empty", "structured_chaos"
        ]
        
    def run(self, response_type: str = "random", size: int = 100, *args, **kwargs) -> str:
        if response_type == "random":
            response_type = random.choice(self.response_types)
            
        if response_type == "random_string":
            return ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=size))
        elif response_type == "malformed_json":
            return '{"key": "value", "incomplete": '
        elif response_type == "unicode_chaos":
            unicode_chars = ['🚀', '🔥', '💯', '🎯', '✨', '🌟', '⭐', '🎉', '🎊', '🎈']
            return ''.join(random.choices(unicode_chars, k=min(size, 50)))
        elif response_type == "large_response":
            return "LARGE_DATA: " + "x" * size
        elif response_type == "empty":
            return ""
        elif response_type == "structured_chaos":
            return f"{{\"random\": {random.randint(1, 1000)}, \"data\": \"{'x' * size}\"}} EXTRA_TEXT"
        else:
            return f"Unknown response type: {response_type}"


# =============================================================================
# MEMORY GROWTH TESTING TOOLS
# =============================================================================

class MemoryGrowthInput(BaseModel):
    size: int = Field(default=1000, description="Base memory allocation size")
    growth_factor: float = Field(default=1.0, description="Memory growth multiplier")


class MemoryGrowthTool(BaseTool):
    """
    Tool that simulates memory growth patterns for stress testing.
    
    Different from MemoryIntensiveTool:
    - Tracks cumulative memory usage
    - Configurable growth patterns
    - Memory leak simulation
    - Resource exhaustion testing
    """
    
    name: str = "memory_growth_tool"
    description: str = "Tool that simulates memory growth patterns for stress testing"
    args_schema = MemoryGrowthInput
    
    def __init__(self, name: str = "memory_growth_tool"):
        self.name = name
        self.memory_usage = []
        self.call_count = 0
    
    def run(self, size: int = 1000, growth_factor: float = 1.0, *args, **kwargs) -> str:
        self.call_count += 1
        # Simulate memory consumption with growth
        allocation_size = int(size * (growth_factor ** self.call_count))
        data = "x" * allocation_size
        self.memory_usage.append(data)
        
        total_memory = sum(len(allocation) for allocation in self.memory_usage)
        return f"Allocated {allocation_size} bytes, total: {total_memory} bytes, calls: {self.call_count}"


# =============================================================================
# STATEFUL CORRUPTION TESTING TOOLS
# =============================================================================

class StatefulOperationInput(BaseModel):
    action: str = Field(..., description="Action to perform (increment/set/get/lock/reset)")
    key: Optional[str] = Field(None, description="Key for data operations")
    value: Optional[str] = Field(None, description="Value for set operations")


class StatefulCorruptionTool(BaseTool):
    """
    Tool with complex internal state that can become corrupted.
    
    Simulates:
    - State corruption scenarios
    - Lock contention
    - Data consistency issues
    - Recovery mechanisms
    """
    
    name: str = "stateful_tool"
    description: str = "Tool with complex internal state for corruption testing"
    args_schema = StatefulOperationInput
    
    def __init__(self, name: str = "stateful_tool"):
        self.name = name
        self.state = {"counter": 0, "data": {}, "locked": False}
    
    def run(self, action: str, key: Optional[str] = None, 
            value: Optional[str] = None, *args, **kwargs) -> str:
        if self.state["locked"]:
            raise RuntimeError(f"Tool {self.name} is locked")
        
        if action == "increment":
            self.state["counter"] += 1
            return f"Counter: {self.state['counter']}"
        elif action == "set" and key and value:
            self.state["data"][key] = value
            return f"Set {key}={value}"
        elif action == "get" and key:
            return self.state["data"].get(key, "NOT_FOUND")
        elif action == "lock":
            self.state["locked"] = True
            return "Tool locked"
        elif action == "reset":
            self.state = {"counter": 0, "data": {}, "locked": False}
            return "State reset"
        else:
            return f"Unknown action: {action}"


# =============================================================================
# FACTORY FUNCTIONS FOR STRESS TESTING
# =============================================================================

def create_concurrency_test_tools() -> list[BaseTool]:
    """
    Create tools for concurrency and race condition testing.
    
    Returns:
        List of tools designed for concurrent execution testing
    """
    return [
        RacyTool("race_detector_1"),
        RacyTool("race_detector_2"),
        VariableDelayTool("delay_tool_1", 0.5),
        VariableDelayTool("delay_tool_2", 1.0),
    ]


def create_parser_stress_tools() -> list[BaseTool]:
    """
    Create tools for parser stress testing.
    
    Returns:
        List of tools that generate challenging parser inputs
    """
    return [
        RandomResponseTool("chaos_generator_1"),
        RandomResponseTool("chaos_generator_2"),
        MemoryGrowthTool("memory_bomber"),
    ]


def create_stateful_corruption_tools() -> list[BaseTool]:
    """
    Create tools for stateful corruption testing.
    
    Returns:
        List of tools with complex state for corruption testing
    """
    return [
        StatefulCorruptionTool("stateful_primary"),
        StatefulCorruptionTool("stateful_secondary"),
        MemoryGrowthTool("memory_tracker"),
    ]


def create_comprehensive_stress_tools() -> list[BaseTool]:
    """
    Create a comprehensive set of stress testing tools.
    
    Returns:
        Complete toolkit for stress testing scenarios
    """
    return [
        RacyTool("concurrent_counter"),
        VariableDelayTool("timeout_simulator", 2.0),
        RandomResponseTool("parser_stressor"),
        MemoryGrowthTool("memory_pressure"),
        StatefulCorruptionTool("state_corruptor"),
    ]
