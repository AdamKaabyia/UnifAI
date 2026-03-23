"""
Professional concurrent execution testing tools and fixtures.

This module provides specialized tools for testing concurrent execution patterns,
resource contention, semaphore behavior, and performance characteristics.
"""

import asyncio
import threading
import time
import tempfile
import os
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from mas.elements.tools.common.base_tool import BaseTool


# Shared Resources for Testing
class SharedCounter:
    """Thread-safe counter for testing concurrent access."""
    
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()
        self._access_log = []
        
    def increment(self, tool_id: str) -> int:
        """Increment counter and log access."""
        with self._lock:
            self._value += 1
            self._access_log.append({
                'tool_id': tool_id,
                'value': self._value,
                'timestamp': time.time(),
                'thread_id': threading.current_thread().ident
            })
            return self._value
    
    def get_value(self) -> int:
        with self._lock:
            return self._value
    
    def get_access_log(self) -> list:
        with self._lock:
            return self._access_log.copy()
    
    def reset(self):
        with self._lock:
            self._value = 0
            self._access_log.clear()


class SharedFileResource:
    """Shared file resource for testing file contention."""
    
    def __init__(self):
        self._temp_file = tempfile.NamedTemporaryFile(mode='w+', delete=False)
        self._temp_file.close()
        self.file_path = self._temp_file.name
        self._access_log = []
        self._lock = threading.Lock()
        
    def write_data(self, tool_id: str, data: str) -> str:
        """Write data to shared file."""
        with self._lock:
            try:
                with open(self.file_path, 'a') as f:
                    f.write(f"[{tool_id}] {data}\n")
                self._access_log.append({
                    'tool_id': tool_id,
                    'operation': 'write',
                    'data': data,
                    'timestamp': time.time()
                })
                return f"Written: {data}"
            except Exception as e:
                return f"Error: {e}"
    
    def read_data(self, tool_id: str) -> str:
        """Read data from shared file."""
        with self._lock:
            try:
                with open(self.file_path, 'r') as f:
                    content = f.read()
                self._access_log.append({
                    'tool_id': tool_id,
                    'operation': 'read',
                    'timestamp': time.time()
                })
                return content
            except Exception as e:
                return f"Error: {e}"
    
    def get_access_log(self) -> list:
        with self._lock:
            return self._access_log.copy()
    
    def cleanup(self):
        """Clean up temporary file."""
        try:
            os.unlink(self.file_path)
        except:
            pass


class ConcurrencyTracker:
    """Track concurrent execution patterns."""
    
    def __init__(self):
        self._active_tools = set()
        self._max_concurrent = 0
        self._execution_log = []
        self._lock = threading.Lock()
        
    def start_execution(self, tool_id: str):
        """Mark tool as starting execution."""
        with self._lock:
            self._active_tools.add(tool_id)
            current_count = len(self._active_tools)
            if current_count > self._max_concurrent:
                self._max_concurrent = current_count
            
            self._execution_log.append({
                'tool_id': tool_id,
                'event': 'start',
                'timestamp': time.time(),
                'concurrent_count': current_count
            })
    
    def end_execution(self, tool_id: str):
        """Mark tool as ending execution."""
        with self._lock:
            self._active_tools.discard(tool_id)
            self._execution_log.append({
                'tool_id': tool_id,
                'event': 'end',
                'timestamp': time.time(),
                'concurrent_count': len(self._active_tools)
            })
    
    def get_max_concurrent(self) -> int:
        with self._lock:
            return self._max_concurrent
    
    def get_execution_log(self) -> list:
        with self._lock:
            return self._execution_log.copy()
    
    def reset(self):
        with self._lock:
            self._active_tools.clear()
            self._max_concurrent = 0
            self._execution_log.clear()


# Pydantic Schemas
class SemaphoreTestInput(BaseModel):
    """Input schema for semaphore testing tools."""
    operation: str = Field(description="Operation to perform")
    duration: float = Field(default=0.1, description="Duration to hold execution")
    tool_id: Optional[str] = Field(default=None, description="Tool identifier")


class ResourceContentionInput(BaseModel):
    """Input schema for resource contention testing."""
    operation: str = Field(description="Operation: 'read', 'write', 'increment'")
    data: Optional[str] = Field(default=None, description="Data for write operations")
    duration: float = Field(default=0.1, description="Duration to hold resource access")


class TimingTestInput(BaseModel):
    """Input schema for timing/performance testing."""
    duration: float = Field(description="Duration to simulate work")
    work_type: str = Field(default="cpu", description="Type of work: 'cpu', 'io', 'mixed'")


# Concurrent Testing Tools
class SemaphoreTestTool(BaseTool):
    """
    Tool for testing semaphore/concurrency limit behavior.
    
    Tracks when it starts and ends execution to verify that
    max_concurrent limits are respected.
    """
    
    name: str = "semaphore_test"
    description: str = "Tool for testing concurrent execution limits"
    args_schema = SemaphoreTestInput
    
    def __init__(self, name: str = "semaphore_test", tracker: Optional[ConcurrencyTracker] = None):
        self.name = name
        self.tracker = tracker or ConcurrencyTracker()
        
    def run(self, operation: str, duration: float = 0.1, tool_id: Optional[str] = None, *args, **kwargs) -> str:
        effective_tool_id = tool_id or f"{self.name}_{int(time.time() * 1000000)}"
        
        # Mark start of execution
        self.tracker.start_execution(effective_tool_id)
        
        try:
            # Simulate work
            time.sleep(duration)
            result = f"Semaphore test completed: {operation} ({duration}s)"
            
        finally:
            # Mark end of execution
            self.tracker.end_execution(effective_tool_id)
            
        return result


class ResourceContentionTool(BaseTool):
    """
    Tool for testing shared resource access patterns.
    
    Tests file access, counter increment, and resource contention.
    """
    
    name: str = "resource_contention"
    description: str = "Tool for testing shared resource access"
    args_schema = ResourceContentionInput
    
    def __init__(self, name: str = "resource_contention", 
                 counter: Optional[SharedCounter] = None,
                 file_resource: Optional[SharedFileResource] = None):
        self.name = name
        self.counter = counter or SharedCounter()
        self.file_resource = file_resource or SharedFileResource()
        
    def run(self, operation: str, data: Optional[str] = None, duration: float = 0.1, *args, **kwargs) -> str:
        tool_id = f"{self.name}_{int(time.time() * 1000000)}"
        
        # Debug: Log what operation is being performed
        print(f"🔧 {self.name}: operation='{operation}', data='{data}', duration={duration}")
        
        # Simulate resource access delay
        time.sleep(duration)
        
        if operation == "increment":
            value = self.counter.increment(tool_id)
            result = f"Counter incremented to: {value}"
            print(f"🔧 {self.name}: {result}")
            return result
        
        elif operation == "write":
            if not data:
                data = f"data_{tool_id}"
            result = self.file_resource.write_data(tool_id, data)
            return result
        
        elif operation == "read":
            result = self.file_resource.read_data(tool_id)
            return f"Read {len(result)} characters from shared file"
        
        else:
            return f"Unknown operation: {operation}"


class TimingTestTool(BaseTool):
    """
    Tool for performance and timing tests.
    
    Simulates different types of work (CPU, I/O, mixed) with
    configurable durations for testing concurrent execution timing.
    """
    
    name: str = "timing_test"
    description: str = "Tool for performance and timing tests"
    args_schema = TimingTestInput
    
    def __init__(self, name: str = "timing_test"):
        self.name = name
        self.start_time = None
        
    def run(self, duration: float, work_type: str = "cpu", *args, **kwargs) -> str:
        self.start_time = time.time()
        
        if work_type == "cpu":
            # CPU-intensive work
            end_time = time.time() + duration
            while time.time() < end_time:
                # Busy wait with some computation
                sum(i * i for i in range(100))
                
        elif work_type == "io":
            # I/O simulation
            time.sleep(duration)
            
        elif work_type == "mixed":
            # Mixed CPU and I/O
            cpu_duration = duration * 0.5
            io_duration = duration * 0.5
            
            # CPU phase
            end_time = time.time() + cpu_duration
            while time.time() < end_time:
                sum(i * i for i in range(50))
            
            # I/O phase
            time.sleep(io_duration)
            
        else:
            time.sleep(duration)
        
        actual_duration = time.time() - self.start_time
        return f"Completed {work_type} work in {actual_duration:.3f}s (target: {duration}s)"


# Factory Functions
def create_semaphore_testing_tools(count: int = 5, shared_tracker: Optional[ConcurrencyTracker] = None) -> tuple:
    """
    Create tools for semaphore/concurrency testing.
    
    Returns:
        tuple: (tools_list, shared_tracker)
    """
    if shared_tracker is None:
        shared_tracker = ConcurrencyTracker()
    
    tools = []
    for i in range(count):
        tool = SemaphoreTestTool(f"semaphore_test_{i}", shared_tracker)
        tools.append(tool)
    
    return tools, shared_tracker


def create_resource_contention_tools(count: int = 3) -> tuple:
    """
    Create tools for resource contention testing.
    
    Returns:
        tuple: (tools_list, shared_counter, shared_file_resource)
    """
    shared_counter = SharedCounter()
    shared_file_resource = SharedFileResource()
    
    tools = []
    for i in range(count):
        tool = ResourceContentionTool(
            f"resource_tool_{i}", 
            shared_counter, 
            shared_file_resource
        )
        tools.append(tool)
    
    return tools, shared_counter, shared_file_resource


def create_timing_test_tools(work_types: list = None) -> list:
    """
    Create tools for timing/performance testing.
    
    Args:
        work_types: List of work types to create tools for
        
    Returns:
        List of timing test tools
    """
    if work_types is None:
        work_types = ["cpu", "io", "mixed"]
    
    tools = []
    for work_type in work_types:
        tool = TimingTestTool(f"timing_{work_type}")
        tools.append(tool)
    
    return tools


def create_comprehensive_concurrent_tools() -> dict:
    """
    Create a comprehensive set of concurrent testing tools.
    
    Returns:
        Dictionary with all tool types and shared resources
    """
    semaphore_tools, tracker = create_semaphore_testing_tools(10)  # Create more tools for comprehensive testing
    resource_tools, counter, file_resource = create_resource_contention_tools(3)
    timing_tools = create_timing_test_tools()
    
    return {
        'semaphore_tools': semaphore_tools,
        'resource_tools': resource_tools,
        'timing_tools': timing_tools,
        'all_tools': semaphore_tools + resource_tools + timing_tools,
        'tracker': tracker,
        'counter': counter,
        'file_resource': file_resource
    }
