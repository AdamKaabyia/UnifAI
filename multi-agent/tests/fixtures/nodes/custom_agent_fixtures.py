"""
Fixtures specific to CustomAgentNode testing.

Provides fixtures for creating and configuring custom agents.
"""

import pytest
from typing import List
from unittest.mock import Mock

from mas.elements.tools.common.base_tool import BaseTool


@pytest.fixture
def custom_agent_tools():
    """
    Create tools commonly used by custom agents.
    
    Returns:
        List of mock tools suitable for custom agents
    """
    tools = []
    
    # Data analysis tool
    tool1 = Mock(spec=BaseTool)
    tool1.name = "analyze_data"
    tool1.description = "Analyzes data patterns and trends"
    tools.append(tool1)
    
    # Report generation tool
    tool2 = Mock(spec=BaseTool)
    tool2.name = "generate_report"
    tool2.description = "Generates formatted reports"
    tools.append(tool2)
    
    # Database query tool
    tool3 = Mock(spec=BaseTool)
    tool3.name = "query_database"
    tool3.description = "Queries database for information"
    tools.append(tool3)
    
    return tools


@pytest.fixture
def custom_agent_with_state(state_view, custom_agent_tools):
    """
    Create a CustomAgentNode with state and context configured.
    
    Returns:
        Configured CustomAgentNode instance
    """
    from tests.factories.node_factory import NodeFactory
    from tests.fixtures.common.llm_fixtures import create_mock_llm
    
    return NodeFactory.create_custom_agent(
        llm=create_mock_llm(),
        state=state_view,
        uid="test_agent",
        tools=custom_agent_tools,
        system_message="I am a test custom agent",
        strategy_type="react"
    )
