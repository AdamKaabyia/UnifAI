"""
Mock tools for unit and integration testing.

This module provides simple, predictable mock tools for testing basic
functionality without complex failure modes or edge cases.
"""

from typing import Any, Optional, Dict, List
from pydantic import BaseModel, Field
from mas.elements.tools.common.base_tool import BaseTool


# =============================================================================
# BASIC MOCK TOOLS
# =============================================================================

class BasicOperationInput(BaseModel):
    operation: str = Field(default="process", description="Operation to perform")
    data: Optional[str] = Field(None, description="Data to process")


class MockTool(BaseTool):
    """
    Simple, predictable mock tool for basic testing.
    
    Always succeeds with predictable outputs for reliable testing.
    """
    
    name: str = "mock_tool"
    description: str = "Simple mock tool for basic testing"
    args_schema = BasicOperationInput
    
    def __init__(self, name: str = "mock_tool", custom_description: str = "Mock tool"):
        self.name = name
        self.description = custom_description
        self.call_count = 0
        
    def run(self, operation: str = "process", data: Optional[str] = None, *args, **kwargs) -> str:
        self.call_count += 1
        if data:
            return f"Mock result from {self.name}: processed '{data}' (call #{self.call_count})"
        else:
            return f"Mock result from {self.name}: {operation} (call #{self.call_count})"


class CalculatorInput(BaseModel):
    operation: str = Field(..., description="Math operation (add/subtract/multiply/divide)")
    a: float = Field(..., description="First number")
    b: float = Field(..., description="Second number")


class MockCalculatorTool(BaseTool):
    """Mock calculator tool for testing tool calls with structured inputs."""
    
    name: str = "calculator"
    description: str = "Mock calculator tool for basic math operations"
    args_schema = CalculatorInput
    
    def run(self, operation: str, a: float, b: float, *args, **kwargs) -> str:
        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                return "Error: Division by zero"
            result = a / b
        else:
            return f"Error: Unknown operation {operation}"
        
        return f"{operation}({a}, {b}) = {result}"


class SearchInput(BaseModel):
    query: str = Field(..., description="Search query")
    limit: int = Field(default=5, description="Maximum number of results")


class MockSearchTool(BaseTool):
    """Mock search tool for testing information retrieval scenarios."""
    
    name: str = "search_tool"
    description: str = "Mock search tool for information retrieval testing"
    args_schema = SearchInput
    
    def __init__(self, name: str = "search_tool"):
        self.name = name
        
    def run(self, query: str, limit: int = 5, *args, **kwargs) -> str:
        # Generate mock search results
        results = [
            f"Result {i+1}: Information about '{query}' from source {i+1}"
            for i in range(min(limit, 3))  # Always return 1-3 results
        ]
        return f"Search results for '{query}': {'; '.join(results)}"


# =============================================================================
# CONFIGURABLE MOCK TOOLS
# =============================================================================

class ConfigurableMockTool(BaseTool):
    """
    Highly configurable mock tool for complex testing scenarios.
    
    Can be configured to:
    - Return specific responses
    - Fail on certain inputs
    - Track call history
    - Simulate various behaviors
    """
    
    name: str = "configurable_mock"
    description: str = "Configurable mock tool for complex testing scenarios"
    args_schema = BasicOperationInput
    
    def __init__(self, name: str = "configurable_mock", 
                 responses: Optional[Dict[str, str]] = None,
                 failure_inputs: Optional[List[str]] = None,
                 should_fail: bool = False):
        self.name = name
        self.responses = responses or {}
        self.failure_inputs = failure_inputs or []
        self.should_fail = should_fail
        self.call_history: List[Dict[str, Any]] = []
        
    def run(self, operation: str = "process", data: Optional[str] = None, *args, **kwargs) -> str:
        # Record call
        call_info = {"operation": operation, "data": data, "args": args, "kwargs": kwargs}
        self.call_history.append(call_info)
        
        # Check for configured failures
        if self.should_fail or operation in self.failure_inputs:
            raise RuntimeError(f"Configured failure for operation: {operation}")
        
        # Return configured response if available
        if operation in self.responses:
            return self.responses[operation]
        
        # Default response
        if data:
            return f"Configurable mock {self.name}: processed '{data}' with {operation}"
        else:
            return f"Configurable mock {self.name}: executed {operation}"


# =============================================================================
# FACTORY FUNCTIONS FOR MOCK TOOLS
# =============================================================================

def create_basic_mock_tools() -> List[BaseTool]:
    """
    Create a basic set of mock tools for simple testing.
    
    Returns:
        List of simple, reliable mock tools
    """
    return [
        MockTool("basic_tool_1"),
        MockTool("basic_tool_2"),
        MockCalculatorTool(),
        MockSearchTool(),
    ]


def create_react_demo_tools() -> List[BaseTool]:
    """
    Create tools commonly used in ReAct demonstrations.
    
    Returns:
        List of tools that simulate common ReAct scenarios
    """
    return [
        MockCalculatorTool(),
        MockSearchTool(),
        MockTool("data_processor", "Tool for processing data"),
        MockTool("file_manager", "Tool for file operations"),
    ]


def create_configurable_test_suite(scenarios: Dict[str, Dict[str, Any]]) -> List[BaseTool]:
    """
    Create a suite of configurable mock tools for specific test scenarios.
    
    Args:
        scenarios: Dict mapping tool names to configuration dicts
        
    Returns:
        List of configured mock tools
    """
    tools = []
    for tool_name, config in scenarios.items():
        tool = ConfigurableMockTool(
            name=tool_name,
            responses=config.get("responses", {}),
            failure_inputs=config.get("failure_inputs", []),
            should_fail=config.get("should_fail", False)
        )
        tools.append(tool)
    return tools


def create_mixed_reliability_tools() -> List[BaseTool]:
    """
    Create tools with mixed reliability for testing error handling.
    
    Returns:
        List of tools with different reliability characteristics
    """
    return [
        MockTool("reliable_tool"),  # Always works
        ConfigurableMockTool("semi_reliable", failure_inputs=["dangerous_operation"]),
        ConfigurableMockTool("unreliable_tool", should_fail=True),
        MockCalculatorTool(),  # Reliable but can have domain errors (div by zero)
    ]
