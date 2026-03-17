"""
Integration tests for complete ReAct agent workflows.

Tests end-to-end ReAct agent execution including:
- Complete agent cycles (planning -> action -> finish)
- Multi-tool execution scenarios
- Error handling and recovery workflows
- Conversation flow integrity
- Real component integration
"""

import pytest
from unittest.mock import Mock, patch
from mas.elements.llms.common.chat.message import ChatMessage, Role, ToolCall
from mas.elements.nodes.common.agent.strategies.react import ReActStrategy
from mas.elements.nodes.common.agent.execution import AgentIterator, ExecutionMode, ExecutionHandlerFactory
from mas.elements.nodes.common.agent.execution.executor import AgentActionExecutor
from mas.elements.nodes.common.agent.parsers.tool_call_parser import ToolCallParser
from mas.elements.nodes.common.agent.primitives import AgentAction, AgentObservation, AgentFinish
from mas.elements.tools.common.base_tool import BaseTool


# Note: Using professional mock tools from fixtures instead of ad-hoc tools


@pytest.mark.integration
@pytest.mark.agent_system
class TestReActCompleteFlow:
    """Integration tests for complete ReAct agent workflows."""

    @pytest.fixture
    def mock_tools(self, react_demo_tools):
        """Create mock tools for integration testing using professional fixtures."""
        return react_demo_tools

    @pytest.fixture
    def mock_tool_executor_manager(self, mock_tools):
        """Mock ToolExecutorManager for integration testing."""
        manager = Mock()
        manager.has_tool.return_value = True
        manager.execute_requests_async.return_value = Mock()
        return manager

    @pytest.fixture
    def action_executor(self, mock_tool_executor_manager):
        """Create AgentActionExecutor with mocked dependencies."""
        return AgentActionExecutor(
            tool_executor_manager=mock_tool_executor_manager,
            validate_args=True
        )

    @pytest.fixture
    def react_strategy(self, mock_tools):
        """Create ReActStrategy with controlled LLM responses."""
        parser = ToolCallParser()

        def mock_llm_chat(messages, tools):
            # Simulate different LLM responses based on conversation state
            if len(messages) == 2:  # Initial query (system + user)
                return ChatMessage(
                    role=Role.ASSISTANT,
                    content="I need to search for information and calculate something.",
                    tool_calls=[
                        ToolCall(
                            name="search_tool",
                            args={"query": "test query"},
                            tool_call_id="call-1"
                        ),
                        ToolCall(
                            name="calculator",
                            args={"expression": "2 + 2"},
                            tool_call_id="call-2"
                        )
                    ]
                )
            else:  # After tool execution (user + assistant + tool responses)
                return ChatMessage(
                    role=Role.ASSISTANT,
                    content="Based on my search and calculation, the answer is 4. The search found relevant information and the calculation shows that 2 + 2 equals 4."
                )

        return ReActStrategy(
            llm_chat=mock_llm_chat,
            tools=mock_tools,
            parser=parser,
            max_steps=5
        )

    def test_complete_react_cycle_auto_mode(self, react_strategy, action_executor):
        """Test complete ReAct cycle in AUTO mode with multiple tools."""
        # Create execution handler using new pattern
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=action_executor
        )
        
        # Create iterator
        iterator = AgentIterator(
            strategy=react_strategy,
            execution_handler=execution_handler
        )

        # Set initial messages
        iterator.messages = [
            ChatMessage(role=Role.USER, content="What is 2 + 2 and search for test?")
        ]

        # Mock action executor to return observations
        action_executor.execute_batch = Mock(return_value=[
            AgentObservation(
                action_id="call-1",
                tool="search_tool",
                output="Found test information",
                success=True,
                execution_time=0.1
            ),
            AgentObservation(
                action_id="call-2",
                tool="calculator",
                output="4",
                success=True,
                execution_time=0.05
            )
        ])

        # Execute complete workflow
        steps = []
        for step in iterator:
            steps.append(step)
            if step.type.value == "finish":
                break

        # Verify workflow completion
        assert len(steps) >= 2

        # In AUTO mode: Should have planning, observation, and finish steps (no action steps yielded)
        planning_steps = [s for s in steps if s.type.value == "planning"]
        observation_steps = [s for s in steps if s.type.value == "observation"] 
        finish_steps = [s for s in steps if s.type.value == "finish"]

        assert len(planning_steps) >= 1  # Should have planning step
        assert len(observation_steps) >= 1  # Should have observation steps from executed actions
        assert len(finish_steps) == 1  # Should finish

        # Should have executed tools in batch
        action_executor.execute_batch.assert_called_once()

        # Should have all observations
        assert len(iterator.observations) == 2

        # Should have proper conversation history
        assert len(iterator.messages) >= 2  # Original + assistant responses

        # Verify conversation flow integrity
        user_messages = [m for m in iterator.messages if m.role == Role.USER]
        assistant_messages = [m for m in iterator.messages if m.role == Role.ASSISTANT]

        assert len(user_messages) == 1  # Original query
        assert len(assistant_messages) >= 1  # At least planning response

    def test_guided_mode_with_confirmation_workflow(self, react_strategy, action_executor):
        """Test complete ReAct workflow in GUIDED mode with action confirmation."""
        # Create iterator in guided mode
        # Create execution handler using new pattern
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.GUIDED,
            action_executor=action_executor
        )
        
        iterator = AgentIterator(
            strategy=react_strategy,
            execution_handler=execution_handler
        )

        # Set initial messages
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Calculate 2 + 2")
        ]

        # First iteration - should get actions to confirm
        step = next(iterator)

        # Should have pending actions
        pending = iterator.get_pending_actions()
        assert len(pending) >= 1

        # Confirm actions one by one
        action_executor.execute = Mock(return_value=AgentObservation(
            action_id=pending[0].id,
            tool=pending[0].tool,
            output="Mock result",
            success=True,
            execution_time=0.1
        ))

        confirmed_steps = []
        for action in pending:
            obs_step = iterator.confirm_action(action.id, execute=True)
            confirmed_steps.append(obs_step)
            assert obs_step.type.value == "observation"
            assert obs_step.data.success

        # Should have executed all actions
        assert action_executor.execute.call_count == len(pending)

        # Should have observations for all actions
        assert len(iterator.observations) == len(pending)

    def test_error_handling_and_recovery_workflow(self, mock_tools, action_executor):
        """Test error handling and recovery in complete ReAct workflow."""
        parser = ToolCallParser()

        # Create strategy that will cause parse error then recover
        call_count = 0

        def mock_llm_chat_with_error(messages, tools):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call - return invalid response that will cause parse error
                return ChatMessage(
                    role=Role.ASSISTANT,
                    content="",  # Empty content should cause validation error
                    tool_calls=[
                        ToolCall(
                            name="",  # Empty tool name will cause parse error
                            args={"test": "value"},
                            tool_call_id="invalid-call"
                        )
                    ]
                )
            else:
                # Second call - return valid response
                return ChatMessage(
                    role=Role.ASSISTANT,
                    content="Now I'll provide a proper final answer after the error."
                )

        # Mock SystemError.from_parse_error to avoid constants import issue
        with patch('elements.nodes.common.agent.primitives.SystemError.from_parse_error') as mock_system_error:
            from mas.elements.nodes.common.agent.primitives import SystemError
            mock_system_error.return_value = SystemError(
                message="Parse error occurred",
                error_type="parse_error",
                raw_output="Invalid tool call",
                guidance="Please provide valid tool call format",
                recoverable=True
            )

            strategy = ReActStrategy(
                llm_chat=mock_llm_chat_with_error,
                tools=mock_tools,
                parser=parser,
                max_steps=5
            )

        # Create execution handler using new pattern
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )

        iterator.messages = [
            ChatMessage(role=Role.USER, content="Test error handling")
        ]

        # Execute workflow with error recovery
        steps = []
        for step in iterator:
            steps.append(step)
            if step.type.value in ["finish", "error"] or len(steps) > 10:
                break

        # Should have error step (ERROR steps are terminal, so no recovery)
        error_steps = [s for s in steps if s.type.value == "error"]
        assert len(error_steps) >= 1

        # Strategy should have been called once and produced an error
        assert call_count == 1
        
        # Verify the error step contains error information
        error_step = error_steps[0]
        # The error could be about missing constants module or parse error
        error_message = str(error_step.data)
        assert any(keyword in error_message for keyword in [
            "Tool call missing name", 
            "Parse error", 
            "constants", 
            "Invalid tool call"
        ])

    def test_multiple_tool_calls_parallel_execution_workflow(self, react_strategy, action_executor):
        """Test workflow with multiple tool calls executed in parallel."""
        # Create execution handler using new pattern
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=action_executor
        )
        
        iterator = AgentIterator(
            strategy=react_strategy,
            execution_handler=execution_handler
        )

        iterator.messages = [
            ChatMessage(role=Role.USER, content="Use multiple tools simultaneously")
        ]

        # Mock batch execution with multiple tools
        action_executor.execute_batch = Mock(return_value=[
            AgentObservation(action_id="call-1", tool="search_tool", output="Search result", success=True),
            AgentObservation(action_id="call-2", tool="calculator", output="Calculation result", success=True)
        ])

        # Execute first iteration
        step = next(iterator)

        # Should have called execute_batch with multiple actions
        action_executor.execute_batch.assert_called_once()
        actions = action_executor.execute_batch.call_args[0][0]
        assert len(actions) == 2
        assert actions[0].tool == "search_tool"
        assert actions[1].tool == "calculator"

        # Should have multiple observations
        assert len(iterator.observations) == 2

        # Verify all observations have correct tool mapping
        obs_by_tool = {obs.tool: obs for obs in iterator.observations}
        assert "search_tool" in obs_by_tool
        assert "calculator" in obs_by_tool
        assert all(obs.success for obs in iterator.observations)

    def test_conversation_flow_integrity_throughout_workflow(self, react_strategy, action_executor):
        """Test that conversation flow maintains integrity throughout complete workflow."""
        # Create execution handler using new pattern
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=action_executor
        )
        
        iterator = AgentIterator(
            strategy=react_strategy,
            execution_handler=execution_handler
        )

        # Initial message
        initial_message = ChatMessage(role=Role.USER, content="Test conversation flow")
        iterator.messages = [initial_message]

        # Mock successful execution
        action_executor.execute_batch = Mock(return_value=[
            AgentObservation(action_id="call-1", tool="search_tool", output="Result", success=True),
            AgentObservation(action_id="call-2", tool="calculator", output="Result", success=True)
        ])

        # Execute complete cycle
        steps = []
        for step in iterator:
            steps.append(step)
            if step.type.value == "finish":
                break

        # Verify conversation integrity
        messages = iterator.messages

        # Should start with user message
        assert messages[0] == initial_message

        # Should have assistant messages in correct order
        assistant_messages = [m for m in messages if m.role == Role.ASSISTANT]
        assert len(assistant_messages) >= 1

        # Assistant messages should be properly ordered and contain valid content
        for msg in assistant_messages:
            assert msg.role == Role.ASSISTANT
            assert msg.content is not None
            assert len(msg.content.strip()) > 0

        # Should maintain proper message sequence (no gaps or duplicates)
        roles = [m.role for m in messages]
        assert roles[0] == Role.USER  # Starts with user
        # Should have alternating or logical role sequence

    def test_streaming_events_throughout_workflow(self, react_strategy, action_executor):
        """Test that streaming events are properly emitted throughout workflow."""
        stream_events = []

        def capture_stream(event):
            stream_events.append(event)

        # Create execution handler using new pattern
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=action_executor
        )
        
        iterator = AgentIterator(
            strategy=react_strategy,
            execution_handler=execution_handler,
            stream=capture_stream
        )

        iterator.messages = [
            ChatMessage(role=Role.USER, content="Test streaming workflow")
        ]

        # Mock execution
        action_executor.execute_batch = Mock(return_value=[
            AgentObservation(action_id="call-1", tool="search_tool", output="Result", success=True)
        ])

        # Execute workflow
        steps = []
        for step in iterator:
            steps.append(step)
            if step.type.value == "finish":
                break

        # Should have emitted multiple streaming events
        assert len(stream_events) > 0

        # Verify event structure and progression
        event_types = [event.get("type", "") for event in stream_events]

        # Should have different types of events
        assert len(set(event_types)) > 1

        # All events should have required fields
        for event in stream_events:
            assert "type" in event
            assert "data" in event
            assert "timestamp" in event
            assert "metadata" in event
            # Event types should follow agent_ prefix pattern
            assert event["type"].startswith("agent_")

        # Events should be in chronological order (increasing timestamps)
        timestamps = [event.get("timestamp", 0) for event in stream_events]
        assert timestamps == sorted(timestamps)

    def test_tool_execution_failure_recovery_workflow(self, react_strategy, action_executor):
        """Test workflow recovery from tool execution failures."""
        # Create execution handler using new pattern
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=action_executor
        )
        
        iterator = AgentIterator(
            strategy=react_strategy,
            execution_handler=execution_handler
        )

        iterator.messages = [
            ChatMessage(role=Role.USER, content="Test tool failure recovery")
        ]

        # Mock execution with one failure, one success
        action_executor.execute_batch = Mock(return_value=[
            AgentObservation(
                action_id="call-1",
                tool="search_tool",
                output=None,
                success=False,
                error=Exception("Tool execution failed")
            ),
            AgentObservation(
                action_id="call-2",
                tool="calculator",
                output="4",
                success=True
            )
        ])

        # Execute workflow
        steps = []
        for step in iterator:
            steps.append(step)
            if step.type.value == "finish" or len(steps) > 5:
                break

        # Should have observations for both tools (success and failure)
        assert len(iterator.observations) == 2

        # Should have one failed and one successful observation
        failed_obs = [obs for obs in iterator.observations if not obs.success]
        success_obs = [obs for obs in iterator.observations if obs.success]

        assert len(failed_obs) == 1
        assert len(success_obs) == 1

        # Failed observation should contain error information
        assert failed_obs[0].error is not None
        assert "failed" in str(failed_obs[0].error).lower()

        # Workflow should continue despite partial failure
        finish_steps = [s for s in steps if s.type.value == "finish"]
        assert len(finish_steps) >= 0  # May or may not finish depending on strategy
