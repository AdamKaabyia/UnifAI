"""
Base test class for unit tests.

Provides common setup/teardown and utilities specific to unit testing,
emphasizing isolation, mocking, and focused component testing.
"""

import pytest
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, MagicMock, patch


class BaseUnitTest:
    """
    Base class for unit tests.
    
    Unit tests verify individual components in isolation with heavy use of
    mocking and minimal dependencies on other components.
    
    This class provides utilities for creating mocks, patching dependencies,
    and verifying component behavior in isolation.
    """
    
    def create_mock_state(self) -> Mock:
        """
        Create a mock StateView for unit testing.
        
        Returns:
            Mock StateView with common attributes
        """
        mock_state = Mock()
        mock_state.user_prompt = ""
        mock_state.messages = []
        mock_state.nodes_output = {}
        mock_state.output = ""
        mock_state.inter_packets = []
        mock_state.task_threads = {}
        mock_state.threads = {}
        mock_state.workspaces = {}
        return mock_state
    
    def create_mock_llm(self, response_content: str = "Mock response") -> Mock:
        """
        Create a mock LLM for unit testing.
        
        Args:
            response_content: Default response content
            
        Returns:
            Mock LLM with chat method
        """
        from mas.elements.llms.common.chat.message import ChatMessage, Role
        
        mock_llm = Mock()
        mock_llm.chat.return_value = ChatMessage(
            role=Role.ASSISTANT,
            content=response_content
        )
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.name = "mock_llm"
        return mock_llm
    
    def create_mock_workload_service(self) -> Mock:
        """
        Create a mock workload service for unit testing.
        
        Returns:
            Mock workload service with common methods
        """
        service = Mock()
        
        # Mock workspace
        mock_workspace = Mock()
        mock_workspace.variables = {}
        mock_workspace.context = Mock()
        mock_workspace.context.facts = []
        mock_workspace.context.tasks = []
        mock_workspace.context.results = []
        
        service.get_workspace.return_value = mock_workspace
        service.update_workspace = Mock()
        service.get_thread.return_value = None
        service.save_thread = Mock()
        
        return service
    
    def create_mock_tools(self, count: int = 3) -> List[Mock]:
        """
        Create mock tools for unit testing.
        
        Args:
            count: Number of mock tools to create
            
        Returns:
            List of mock tools
        """
        tools = []
        for i in range(count):
            tool = Mock()
            tool.name = f"mock_tool_{i}"
            tool.description = f"Mock tool {i} for testing"
            tool.run.return_value = f"Result from mock_tool_{i}"
            tools.append(tool)
        return tools
    
    def assert_method_called_with_pattern(
        self,
        mock_obj: Mock,
        method_name: str,
        **expected_kwargs
    ):
        """
        Assert method was called with arguments matching a pattern.
        
        Args:
            mock_obj: Mock object
            method_name: Name of the method
            **expected_kwargs: Expected keyword arguments
        """
        method = getattr(mock_obj, method_name)
        assert method.called, f"{method_name} was not called"
        
        # Check if any call matches the expected pattern
        calls = method.call_args_list
        
        for call in calls:
            call_kwargs = call[1] if len(call) > 1 else {}
            matches = all(
                call_kwargs.get(key) == value
                for key, value in expected_kwargs.items()
            )
            if matches:
                return
        
        raise AssertionError(
            f"{method_name} was not called with expected kwargs: {expected_kwargs}\n"
            f"Actual calls: {calls}"
        )
    
    def capture_method_calls(self, obj: Any, method_name: str):
        """
        Context manager to capture and return method calls.
        
        Args:
            obj: Object to patch
            method_name: Method name to capture
            
        Returns:
            Context manager that yields list of calls
        """
        calls = []
        
        original_method = getattr(obj, method_name)
        
        def capturing_method(*args, **kwargs):
            calls.append({'args': args, 'kwargs': kwargs})
            return original_method(*args, **kwargs)
        
        class CallCapture:
            def __enter__(self):
                setattr(obj, method_name, capturing_method)
                return calls
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                setattr(obj, method_name, original_method)
        
        return CallCapture()
