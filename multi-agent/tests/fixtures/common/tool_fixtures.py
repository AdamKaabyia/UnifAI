"""
Fixtures for tool mocks and test tools.

Provides fixtures for creating mock tools and test tool collections.
"""

import pytest
from typing import List
from unittest.mock import Mock
from pydantic import BaseModel, Field

from mas.elements.tools.common.base_tool import BaseTool


class TestToolInput(BaseModel):
    """Input schema for basic test tools."""
    query: str = Field(..., description="Query or input for the tool")
    

class BasicTestTool(BaseTool):
    """Basic test tool for simple testing scenarios."""
    
    name: str = "test_tool"
    description: str = "A basic test tool"
    args_schema = TestToolInput
    
    def __init__(self, name: str = "test_tool", result: str = "Test result"):
        self.name = name
        self.result = result
        
    def run(self, query: str, **kwargs) -> str:
        """Execute the tool."""
        return f"{self.result}: {query}"


def create_basic_test_tools(count: int = 3) -> List[BaseTool]:
    """
    Create a list of basic test tools.
    
    Args:
        count: Number of tools to create
        
    Returns:
        List of BasicTestTool instances
    """
    return [
        BasicTestTool(
            name=f"test_tool_{i}",
            result=f"Result from tool {i}"
        )
        for i in range(1, count + 1)
    ]


@pytest.fixture
def mock_tools():
    """
    Mock tools for testing.
    
    Returns:
        List of 3 mock tools
    """
    tool1 = Mock(spec=BaseTool)
    tool1.name = "test_tool"
    tool1.description = "A test tool"
    
    tool2 = Mock(spec=BaseTool)
    tool2.name = "search_tool"
    tool2.description = "A search tool"
    
    tool3 = Mock(spec=BaseTool)
    tool3.name = "calculator"
    tool3.description = "A calculator tool"
    
    return [tool1, tool2, tool3]


@pytest.fixture
def basic_test_tools():
    """
    Create basic test tools for testing.
    
    Returns:
        List of BasicTestTool instances
    """
    return create_basic_test_tools()


@pytest.fixture
def mock_domain_tools():
    """
    Create mock domain tools for testing.
    
    Returns:
        List of mock domain-specific tools
    """
    tool1 = Mock(spec=BaseTool)
    tool1.name = "analyze_data_tool"
    tool1.description = "Analyzes data"
    
    tool2 = Mock(spec=BaseTool)
    tool2.name = "create_report_tool"
    tool2.description = "Creates reports"
    
    return [tool1, tool2]


@pytest.fixture
def calculator_tool():
    """
    Individual calculator tool for specific testing.
    
    Returns:
        Mock calculator tool
    """
    from tests.fixtures.mock_tools import MockCalculatorTool
    return MockCalculatorTool()


@pytest.fixture
def search_tool():
    """
    Individual search tool for specific testing.
    
    Returns:
        Mock search tool
    """
    from tests.fixtures.mock_tools import MockSearchTool
    return MockSearchTool()


@pytest.fixture
def basic_mock_tools():
    """
    Simple, reliable mock tools for basic testing.
    
    Returns:
        List of basic mock tools
    """
    from tests.fixtures.mock_tools import create_basic_mock_tools
    return create_basic_mock_tools()


@pytest.fixture
def react_demo_tools():
    """
    Tools commonly used in ReAct demonstrations.
    
    Returns:
        List of ReAct demo tools
    """
    from tests.fixtures.mock_tools import create_react_demo_tools
    return create_react_demo_tools()
