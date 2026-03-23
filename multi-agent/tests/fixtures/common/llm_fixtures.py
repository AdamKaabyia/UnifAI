"""
Fixtures for LLM mocks and test LLMs.

Provides fixtures for creating mock LLMs and predictable LLMs for testing.
"""

import pytest
from typing import List
from unittest.mock import Mock

from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.elements.tools.common.base_tool import BaseTool


def create_mock_llm(response_content: str = "Mock LLM response") -> Mock:
    """
    Create a mock LLM for testing.
    
    Args:
        response_content: Default response content
        
    Returns:
        Mock LLM with chat method configured
    """
    mock_llm = Mock()
    mock_llm.chat.return_value = ChatMessage(
        role=Role.ASSISTANT,
        content=response_content
    )
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.name = "mock_llm"
    mock_llm.stream.return_value = iter([response_content])
    return mock_llm


@pytest.fixture
def mock_llm():
    """
    Create a mock LLM for testing.
    
    Returns:
        Mock LLM instance
    """
    return create_mock_llm()


@pytest.fixture
def mock_llm_chat():
    """
    Mock LLM chat function for agent system testing.
    
    Returns:
        Callable that returns a default ChatMessage
    """
    def _mock_chat(messages: List[ChatMessage], tools: List[BaseTool] = None) -> ChatMessage:
        # Default response with tool call
        from mas.elements.llms.common.chat.message import ToolCall
        return ChatMessage(
            role=Role.ASSISTANT,
            content="I'll search for information.",
            tool_calls=[
                ToolCall(
                    name="test_tool",
                    args={"query": "test"},
                    tool_call_id="test-call-123"
                )
            ]
        )
    return _mock_chat


@pytest.fixture
def mock_llm_provider():
    """
    Mock LLM provider for testing.
    
    Returns:
        Mock provider with common methods
    """
    provider = Mock()
    provider.chat.return_value = ChatMessage(
        role=Role.ASSISTANT,
        content="Mock LLM response"
    )
    provider.stream.return_value = iter(["Mock", " streaming", " response"])
    provider.bind_tools.return_value = provider
    return provider


@pytest.fixture
def predictable_llm():
    """
    Provide a deterministic LLM controller for testing.
    
    Returns:
        PredictableLLM instance from integration fixtures
    """
    from tests.fixtures.orchestrator_integration import PredictableLLM
    return PredictableLLM()
