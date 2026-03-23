"""
Boundary condition tests for ReAct agent workflows.

Tests specific boundary conditions, limits, and edge cases that could
cause system instability or unexpected behavior.

Uses professional testing tools with proper Pydantic schemas from the shared
fixtures library for consistency and reusability across test suites.
"""

import pytest
import json
import time
from mas.elements.llms.common.chat.message import ChatMessage, Role, ToolCall
from mas.elements.nodes.common.agent.strategies.react import ReActStrategy
from mas.elements.nodes.common.agent.execution import AgentIterator, ExecutionMode, ExecutionHandlerFactory
from mas.elements.nodes.common.agent.execution.executor import AgentActionExecutor
from mas.elements.nodes.common.agent.parsers.tool_call_parser import ToolCallParser
from mas.elements.tools.common.execution import ToolExecutorManager, ExecutorConfig
from mas.elements.tools.common.execution.models import ExecutionMode as ToolExecutionMode


@pytest.mark.integration
@pytest.mark.agent_system
class TestReActBoundaryConditions:
    """Boundary condition tests using professional testing tools."""

    @pytest.fixture
    def boundary_action_executor(self, boundary_testing_tools):
        """Create action executor for boundary tests."""
        config = ExecutorConfig(
            max_concurrent=2,
            execution_mode=ToolExecutionMode.CONCURRENT_LIMITED,  # Limited concurrency for boundary testing
            default_timeout=10.0,  # Longer timeout for boundary tests
            enable_circuit_breaker=True
        )
        
        manager = ToolExecutorManager(**config.to_dict())
        manager.set_tools({tool.name: tool for tool in boundary_testing_tools})
        return AgentActionExecutor(tool_executor_manager=manager)

    def test_zero_max_steps_boundary(self, boundary_testing_tools, boundary_action_executor):
        """Test agent behavior with max_steps=0."""
        
        boundary_tool = next(tool for tool in boundary_testing_tools if "boundary" in tool.name)
        
        def zero_steps_llm_chat(messages, tools):
            return ChatMessage(
                role=Role.ASSISTANT,
                content="I should not be able to execute any steps.",
                tool_calls=[
                    ToolCall(
                        name=boundary_tool.name,
                        args={"test_type": "normal"},
                        tool_call_id="zero-1"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=zero_steps_llm_chat,
            tools=boundary_testing_tools,
            parser=ToolCallParser(),
            max_steps=0  # Zero steps allowed
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=boundary_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Try to execute with zero steps")
        ]
        
        steps = []
        
        # Should immediately finish or error due to zero steps
        for step in iterator:
            steps.append(step)
            if len(steps) > 2:  # Safety break
                break
        
        # Should not execute any actions
        action_steps = [s for s in steps if s.type.value == "action"]
        observation_steps = [s for s in steps if s.type.value == "observation"]
        
        assert len(action_steps) == 0  # No actions should be executed
        assert len(observation_steps) == 0  # No observations should be generated

    def test_single_max_step_boundary(self, boundary_testing_tools, boundary_action_executor):
        """Test agent behavior with max_steps=1."""
        
        boundary_tool = next(tool for tool in boundary_testing_tools if "boundary" in tool.name)
        call_count = 0
        
        def single_step_llm_chat(messages, tools):
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                return ChatMessage(
                    role=Role.ASSISTANT,
                    content="I'll execute one action.",
                    tool_calls=[
                        ToolCall(
                            name=boundary_tool.name,
                            args={"test_type": "normal"},
                            tool_call_id="single-1"
                        )
                    ]
                )
            else:
                return ChatMessage(
                    role=Role.ASSISTANT,
                    content="I should not reach this point due to max_steps=1."
                )
        
        strategy = ReActStrategy(
            llm_chat=single_step_llm_chat,
            tools=boundary_testing_tools,
            parser=ToolCallParser(),
            max_steps=1  # Only one step allowed
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=boundary_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Execute with single step limit")
        ]
        
        steps = []
        
        for step in iterator:
            steps.append(step)
            if step.type.value in ["finish", "error"] or len(steps) > 5:
                break
        
        # Should execute exactly one iteration
        assert call_count == 1  # LLM should be called only once
        
        # Should have planning and observation steps
        planning_steps = [s for s in steps if s.type.value == "planning"]
        observation_steps = [s for s in steps if s.type.value == "observation"]
        
        assert len(planning_steps) == 1  # Exactly one planning step
        assert len(observation_steps) >= 1  # At least one observation

    def test_extremely_large_output_handling(self, boundary_testing_tools, boundary_action_executor):
        """Test handling of extremely large tool outputs."""
        
        boundary_tool = next(tool for tool in boundary_testing_tools if "boundary" in tool.name)
        
        def large_output_llm_chat(messages, tools):
            return ChatMessage(
                role=Role.ASSISTANT,
                content="I'll generate a large output to test system limits.",
                tool_calls=[
                    ToolCall(
                        name=boundary_tool.name,
                        args={"test_type": "large_output", "size": 100000},  # 100KB output
                        tool_call_id="large-1"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=large_output_llm_chat,
            tools=boundary_testing_tools,
            parser=ToolCallParser(),
            max_steps=3
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=boundary_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Generate large output")
        ]
        
        steps = []
        observations = []
        
        for step in iterator:
            steps.append(step)
            if step.type.value == "observation":
                observations.append(step.data)
            if step.type.value in ["finish", "error"] or len(steps) > 5:
                break
        
        # Should handle large output gracefully
        assert len(observations) >= 1
        
        # Verify large output was processed
        large_obs = observations[0]
        assert large_obs.success  # Should succeed despite large size
        assert len(large_obs.output) >= 50000  # Should have large output

    def test_unicode_and_special_characters(self, boundary_testing_tools, boundary_action_executor):
        """Test handling of unicode and special characters."""
        
        boundary_tool = next(tool for tool in boundary_testing_tools if "boundary" in tool.name)
        
        def unicode_llm_chat(messages, tools):
            return ChatMessage(
                role=Role.ASSISTANT,
                content="I'll test unicode handling: 🚀🔥💯",
                tool_calls=[
                    ToolCall(
                        name=boundary_tool.name,
                        args={"test_type": "unicode", "size": 100},
                        tool_call_id="unicode-1"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=unicode_llm_chat,
            tools=boundary_testing_tools,
            parser=ToolCallParser(),
            max_steps=3
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=boundary_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Test unicode: 🎯✨🌟")
        ]
        
        steps = []
        observations = []
        
        for step in iterator:
            steps.append(step)
            if step.type.value == "observation":
                observations.append(step.data)
            if step.type.value in ["finish", "error"] or len(steps) > 5:
                break
        
        # Should handle unicode gracefully
        assert len(observations) >= 1
        
        unicode_obs = observations[0]
        assert unicode_obs.success
        assert "🚀" in unicode_obs.output or "🔥" in unicode_obs.output  # Should preserve unicode

    def test_empty_and_null_outputs(self, boundary_testing_tools, boundary_action_executor):
        """Test handling of empty and null tool outputs."""
        
        boundary_tool = next(tool for tool in boundary_testing_tools if "boundary" in tool.name)
        
        def empty_output_llm_chat(messages, tools):
            return ChatMessage(
                role=Role.ASSISTANT,
                content="I'll test empty and null outputs.",
                tool_calls=[
                    ToolCall(
                        name=boundary_tool.name,
                        args={"test_type": "empty"},
                        tool_call_id="empty-1"
                    ),
                    ToolCall(
                        name=boundary_tool.name,
                        args={"test_type": "null"},
                        tool_call_id="null-1"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=empty_output_llm_chat,
            tools=boundary_testing_tools,
            parser=ToolCallParser(),
            max_steps=3
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=boundary_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Test empty and null outputs")
        ]
        
        steps = []
        observations = []
        
        for step in iterator:
            steps.append(step)
            if step.type.value == "observation":
                observations.append(step.data)
            if step.type.value in ["finish", "error"] or len(steps) > 8:
                break
        
        # Should handle empty/null outputs gracefully
        assert len(observations) >= 2
        
        # Both observations should succeed despite empty/null outputs
        for obs in observations:
            assert obs.success  # Should not fail due to empty output

    def test_concurrent_slow_tools_timeout(self, boundary_testing_tools, boundary_action_executor):
        """Test concurrent execution of slow tools with timeouts."""
        
        slow_tool = next(tool for tool in boundary_testing_tools if "slow" in tool.name)
        boundary_tool = next(tool for tool in boundary_testing_tools if "boundary" in tool.name)
        
        def slow_concurrent_llm_chat(messages, tools):
            return ChatMessage(
                role=Role.ASSISTANT,
                content="I'll execute slow tools concurrently.",
                tool_calls=[
                    ToolCall(
                        name=slow_tool.name,
                        args={"delay": 2.0},  # 2 second delay
                        tool_call_id="slow-1"
                    ),
                    ToolCall(
                        name=slow_tool.name,
                        args={"delay": 3.0},  # 3 second delay
                        tool_call_id="slow-2"
                    ),
                    ToolCall(
                        name=boundary_tool.name,
                        args={"test_type": "normal"},  # Fast tool
                        tool_call_id="fast-1"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=slow_concurrent_llm_chat,
            tools=boundary_testing_tools,
            parser=ToolCallParser(),
            max_steps=1  # Only one step to test concurrent execution
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=boundary_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Execute slow tools concurrently")
        ]
        
        start_time = time.time()
        
        steps = []
        observations = []
        
        for step in iterator:
            steps.append(step)
            if step.type.value == "observation":
                observations.append(step.data)
            if step.type.value in ["finish", "error"] or len(steps) > 8:
                break
        
        execution_time = time.time() - start_time
        
        # Should execute concurrently (faster than sequential)
        assert execution_time < 4.0  # Should be ~3s (max of 2s,3s) + overhead, much faster than 2+3=5s sequential
        
        # Should have observations from all tools
        assert len(observations) >= 3
        
        # Fast tool should succeed, slow tools may timeout
        fast_obs = [obs for obs in observations if "Normal output" in str(obs.output)]
        assert len(fast_obs) >= 1  # Fast tool should complete

    def test_memory_intensive_operations(self, boundary_testing_tools, boundary_action_executor):
        """Test handling of memory-intensive operations."""
        
        memory_tool = next(tool for tool in boundary_testing_tools if "memory" in tool.name)
        boundary_tool = next(tool for tool in boundary_testing_tools if "boundary" in tool.name)
        
        def memory_intensive_llm_chat(messages, tools):
            return ChatMessage(
                role=Role.ASSISTANT,
                content="I'll perform memory-intensive operations.",
                tool_calls=[
                    ToolCall(
                        name=memory_tool.name,
                        args={"size_mb": 10},  # 10MB allocation
                        tool_call_id="mem-1"
                    ),
                    ToolCall(
                        name=boundary_tool.name,
                        args={"test_type": "json", "size": 10000},  # Large JSON
                        tool_call_id="json-1"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=memory_intensive_llm_chat,
            tools=boundary_testing_tools,
            parser=ToolCallParser(),
            max_steps=3
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=boundary_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Perform memory-intensive operations")
        ]
        
        steps = []
        observations = []
        
        for step in iterator:
            steps.append(step)
            if step.type.value == "observation":
                observations.append(step.data)
            if step.type.value in ["finish", "error"] or len(steps) > 8:
                break
        
        # Should handle memory-intensive operations
        assert len(observations) >= 2
        
        # Should complete successfully (assuming sufficient system memory)
        successful_ops = [obs for obs in observations if obs.success]
        assert len(successful_ops) >= 1  # At least one should succeed

    def test_rapid_iteration_boundary(self, boundary_testing_tools, boundary_action_executor):
        """Test rapid iteration with minimal delays."""
        
        boundary_tool = next(tool for tool in boundary_testing_tools if "boundary" in tool.name)
        iteration_count = 0
        
        def rapid_iteration_llm_chat(messages, tools):
            nonlocal iteration_count
            iteration_count += 1
            
            if iteration_count <= 5:  # Rapid iterations
                return ChatMessage(
                    role=Role.ASSISTANT,
                    content=f"Rapid iteration {iteration_count}",
                    tool_calls=[
                        ToolCall(
                            name=boundary_tool.name,
                            args={"test_type": "normal"},
                            tool_call_id=f"rapid-{iteration_count}"
                        )
                    ]
                )
            else:
                return ChatMessage(
                    role=Role.ASSISTANT,
                    content="Completed rapid iterations."
                )
        
        strategy = ReActStrategy(
            llm_chat=rapid_iteration_llm_chat,
            tools=boundary_testing_tools,
            parser=ToolCallParser(),
            max_steps=10  # Allow multiple iterations
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=boundary_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Perform rapid iterations")
        ]
        
        start_time = time.time()
        
        steps = []
        observations = []
        
        for step in iterator:
            steps.append(step)
            if step.type.value == "observation":
                observations.append(step.data)
            if step.type.value in ["finish", "error"] or len(steps) > 20:
                break
        
        execution_time = time.time() - start_time
        
        # Should handle rapid iterations efficiently
        assert len(observations) >= 3  # Multiple rapid iterations
        assert execution_time < 5.0  # Should be fast
        
        # All rapid iterations should succeed
        successful_iterations = [obs for obs in observations if obs.success]
        assert len(successful_iterations) >= 3
