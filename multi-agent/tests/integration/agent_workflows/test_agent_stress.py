"""
Stress tests for agent system boundary conditions and race conditions.

Tests extreme scenarios to validate system robustness:
- Very long conversations and context management
- Rapid-fire tool executions
- Memory pressure scenarios
- Timeout and cancellation handling
- Thread safety and race conditions
- Parser stress with malformed data
"""

import pytest
import time
import threading
import random
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor, as_completed
from mas.elements.llms.common.chat.message import ChatMessage, Role, ToolCall
from mas.elements.nodes.common.agent.strategies.react import ReActStrategy
from mas.elements.nodes.common.agent.execution import AgentIterator, ExecutionMode, ExecutionHandlerFactory
from mas.elements.nodes.common.agent.execution.executor import AgentActionExecutor
from mas.elements.nodes.common.agent.parsers.tool_call_parser import ToolCallParser
from mas.elements.nodes.common.agent.primitives import AgentAction, AgentObservation, AgentFinish
from mas.elements.tools.common.base_tool import BaseTool
from mas.elements.tools.common.execution import ToolExecutorManager, ExecutorConfig
from mas.elements.tools.common.execution.models import ExecutionMode as ToolExecutionMode


# Note: Using professional stress testing tools from fixtures instead of ad-hoc tools


@pytest.mark.integration
@pytest.mark.agent_system
@pytest.mark.stress
class TestAgentStress:
    """Stress tests for agent system."""
    
    @pytest.fixture
    def stress_tools(self, stress_testing_tools):
        """Create tools for stress testing using professional fixtures."""
        return stress_testing_tools
    
    @pytest.fixture
    def stress_tool_executor_manager(self, stress_tools):
        """Create ToolExecutorManager for stress testing."""
        # Use default config (no retries for stress testing)
        config = ExecutorConfig(
            max_concurrent=10,
            execution_mode=ToolExecutionMode.PARALLEL,  # High concurrency for stress testing
            default_timeout=1.0,  # Short timeout for stress testing
            enable_circuit_breaker=False,
            enable_metrics=True
        )
        
        manager = ToolExecutorManager(**config.to_dict())
        manager.set_tools({tool.name: tool for tool in stress_tools})
        return manager
    
    @pytest.fixture
    def stress_action_executor(self, stress_tool_executor_manager):
        """Create action executor for stress testing."""
        return AgentActionExecutor(
            tool_executor_manager=stress_tool_executor_manager,
            validate_args=True
        )
    
    def test_very_long_conversation_context(self, stress_tools, stress_action_executor):
        """Test handling of very long conversation contexts."""
        
        # Build a very long conversation history
        long_messages = [
            ChatMessage(role=Role.SYSTEM, content="You are a helpful assistant.")
        ]
        
        # Add 100 user-assistant exchanges
        for i in range(100):
            long_messages.extend([
                ChatMessage(role=Role.USER, content=f"User message {i}: " + "x" * 100),
                ChatMessage(role=Role.ASSISTANT, content=f"Assistant response {i}: " + "y" * 100),
            ])
        
        # Add final user message
        long_messages.append(
            ChatMessage(role=Role.USER, content="Final question after long conversation")
        )
        
        def long_context_llm_chat(messages, tools):
            # Should receive the very long context
            assert len(messages) >= 100
            return ChatMessage(
                role=Role.ASSISTANT,
                content="Handling long context successfully"
            )
        
        strategy = ReActStrategy(
            llm_chat=long_context_llm_chat,
            tools=stress_tools,
            parser=ToolCallParser(),
            max_steps=3
        )
        
        # Create execution handler using new pattern
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=stress_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = long_messages
        
        steps = []
        for step in iterator:
            steps.append(step)
            if step.type.value in ["finish", "error"] or len(steps) > 5:
                break
        
        # Should handle long context without issues
        assert len(steps) >= 1
        assert any(step.type.value == "finish" for step in steps)
    
    def test_rapid_fire_tool_executions(self, stress_tools, stress_action_executor):
        """Test rapid succession of tool executions."""
        
        call_count = 0
        
        def rapid_fire_llm_chat(messages, tools):
            nonlocal call_count
            call_count += 1
            
            if call_count <= 5:  # First 5 calls use tools rapidly
                return ChatMessage(
                    role=Role.ASSISTANT,
                    content=f"Rapid fire call {call_count}",
                    tool_calls=[
                        ToolCall(
                            name="parser_stress_tool",
                            args={"operation": "normal"},
                            tool_call_id=f"rapid-{call_count}"
                        )
                    ]
                )
            else:
                return ChatMessage(
                    role=Role.ASSISTANT,
                    content="Completed rapid fire sequence"
                )
        
        strategy = ReActStrategy(
            llm_chat=rapid_fire_llm_chat,
            tools=stress_tools,
            parser=ToolCallParser(),
            max_steps=10
        )
        
        # Create execution handler using new pattern
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=stress_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Execute tools rapidly")
        ]
        
        start_time = time.time()
        steps = []
        observations = []
        
        for step in iterator:
            steps.append(step)
            if step.type.value == "observation":
                observations.append(step.data)
            
            if step.type.value in ["finish", "error"] or len(steps) > 15:
                break
        
        execution_time = time.time() - start_time
        
        # Should execute multiple tools rapidly
        assert len(observations) >= 3
        assert call_count >= 3
        
        # Should be reasonably fast
        assert execution_time < 2.0
    
    def test_concurrent_iterator_access(self, stress_tools, stress_action_executor):
        """Test thread safety of iterator with concurrent access."""
        
        def concurrent_llm_chat(messages, tools):
            return ChatMessage(
                role=Role.ASSISTANT,
                content="Concurrent access test",
                tool_calls=[
                    ToolCall(
                        name="race_condition_tool",
                        args={"operation": "increment", "use_lock": False},
                        tool_call_id=f"concurrent-{threading.current_thread().ident}"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=concurrent_llm_chat,
            tools=stress_tools,
            parser=ToolCallParser(),
            max_steps=5
        )
        
        # Create multiple iterators
        iterators = []
        for i in range(3):
            # Create execution handler using new pattern
            execution_handler = ExecutionHandlerFactory.create(
                mode=ExecutionMode.AUTO,
                action_executor=stress_action_executor
            )
            
            iterator = AgentIterator(
                strategy=strategy,
                execution_handler=execution_handler
            )
            iterator.messages = [
                ChatMessage(role=Role.USER, content=f"Concurrent test {i}")
            ]
            iterators.append(iterator)
        
        results = []
        
        def run_iterator(iterator, index):
            """Run iterator in separate thread."""
            steps = []
            try:
                for step in iterator:
                    steps.append(step)
                    if step.type.value in ["finish", "error"] or len(steps) > 5:
                        break
                return {"index": index, "steps": steps, "success": True}
            except Exception as e:
                return {"index": index, "error": str(e), "success": False}
        
        # Run iterators concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(run_iterator, iterator, i)
                for i, iterator in enumerate(iterators)
            ]
            
            for future in as_completed(futures):
                results.append(future.result())
        
        # All iterators should complete
        assert len(results) == 3
        
        # Most should succeed (some race conditions might cause failures)
        successful = sum(1 for r in results if r["success"])
        assert successful >= 2  # At least 2 out of 3 should succeed
    
    def test_parser_stress_with_malformed_data(self, stress_tools, stress_action_executor):
        """Stress test parser with various malformed inputs."""
        
        malformed_responses = [
            # Very large content
            ChatMessage(
                role=Role.ASSISTANT,
                content="x" * 50000,  # 50KB of content
                tool_calls=[
                    ToolCall(
                        name="parser_stress_tool",
                        args={"operation": "large_response", "intensity": 10},
                        tool_call_id="large-content"
                    )
                ]
            ),
            
            # Unicode stress
            ChatMessage(
                role=Role.ASSISTANT,
                content="🚀" * 1000,
                tool_calls=[
                    ToolCall(
                        name="parser_stress_tool",
                        args={"operation": "unicode_stress", "intensity": 10},
                        tool_call_id="unicode-stress"
                    )
                ]
            ),
            
            # Deeply nested arguments
            ChatMessage(
                role=Role.ASSISTANT,
                content="Nested data test",
                tool_calls=[
                    ToolCall(
                        name="parser_stress_tool",
                        args={"operation": "json_response", "intensity": 5},
                        tool_call_id="nested-args"
                    )
                ]
            ),
            
            # Many tool calls
            ChatMessage(
                role=Role.ASSISTANT,
                content="Many tool calls",
                tool_calls=[
                    ToolCall(
                        name="parser_stress_tool",
                        args={"operation": "normal", "intensity": i},
                        tool_call_id=f"batch-{i}"
                    )
                    for i in range(20)  # 20 tool calls
                ]
            )
        ]
        
        response_index = 0
        
        def malformed_data_llm_chat(messages, tools):
            nonlocal response_index
            if response_index < len(malformed_responses):
                response = malformed_responses[response_index]
                response_index += 1
                return response
            else:
                return ChatMessage(
                    role=Role.ASSISTANT,
                    content="Completed malformed data stress test"
                )
        
        # Mock SystemError.from_parse_error to handle potential parse errors
        with patch('elements.nodes.common.agent.primitives.SystemError.from_parse_error') as mock_system_error:
            from mas.elements.nodes.common.agent.primitives import SystemError
            mock_system_error.return_value = SystemError(
                message="Parse error in stress test",
                error_type="parse_error",
                raw_output="Malformed data",
                guidance="Handle malformed data gracefully",
                recoverable=True
            )
            
            strategy = ReActStrategy(
                llm_chat=malformed_data_llm_chat,
                tools=stress_tools,
                parser=ToolCallParser(),
                max_steps=10
            )
            
            # Create execution handler using new pattern
            execution_handler = ExecutionHandlerFactory.create(
                mode=ExecutionMode.AUTO,
                action_executor=stress_action_executor
            )
            
            iterator = AgentIterator(
                strategy=strategy,
                execution_handler=execution_handler
            )
            
            iterator.messages = [
                ChatMessage(role=Role.USER, content="Parser stress test")
            ]
            
            steps = []
            observations = []
            errors = []
            
            for step in iterator:
                steps.append(step)
                if step.type.value == "observation":
                    observations.append(step.data)
                elif step.type.value == "error":
                    errors.append(step.data)
                
                if step.type.value in ["finish", "error"] or len(steps) > 30:
                    break
            
            # Should handle malformed data gracefully
            assert len(steps) >= 3
            
            # Should process at least some of the malformed responses
            assert response_index >= 2
            
            # Should have some observations (successful parsing)
            assert len(observations) >= 1
    
    def test_memory_pressure_simulation(self, stress_tools, stress_action_executor):
        """Simulate memory pressure scenarios."""
        
        def memory_pressure_llm_chat(messages, tools):
            return ChatMessage(
                role=Role.ASSISTANT,
                content="Memory pressure test",
                tool_calls=[
                    ToolCall(
                        name="parser_stress_tool",
                        args={"operation": "large_response", "intensity": 10},
                        tool_call_id="memory-pressure"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=memory_pressure_llm_chat,
            tools=stress_tools,
            parser=ToolCallParser(),
            max_steps=5
        )
        
        # Create many iterators to simulate memory pressure
        iterators = []
        for i in range(10):  # 10 concurrent iterators
            # Create execution handler using new pattern
            execution_handler = ExecutionHandlerFactory.create(
                mode=ExecutionMode.AUTO,
                action_executor=stress_action_executor
            )
            
            iterator = AgentIterator(
                strategy=strategy,
                execution_handler=execution_handler
            )
            iterator.messages = [
                ChatMessage(role=Role.USER, content=f"Memory pressure test {i}")
            ]
            iterators.append(iterator)
        
        # Run a few steps on each iterator
        total_steps = 0
        for iterator in iterators:
            steps = 0
            for step in iterator:
                total_steps += 1
                steps += 1
                if steps >= 2 or step.type.value in ["finish", "error"]:
                    break
        
        # Should handle multiple iterators without crashing
        assert total_steps >= 10  # At least one step per iterator
    
    def test_timeout_handling_stress(self, stress_tools, stress_action_executor):
        """Test timeout handling under stress."""
        
        def timeout_llm_chat(messages, tools):
            return ChatMessage(
                role=Role.ASSISTANT,
                content="Testing timeout handling",
                tool_calls=[
                    ToolCall(
                        name="timeout_test_tool",  # This tool has a delay
                        args={"operation": "timeout_test", "intensity": 5},
                        tool_call_id="timeout-test"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=timeout_llm_chat,
            tools=stress_tools,
            parser=ToolCallParser(),
            max_steps=3
        )
        
        # Create execution handler using new pattern
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=stress_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Test timeout handling")
        ]
        
        start_time = time.time()
        steps = []
        
        for step in iterator:
            steps.append(step)
            if step.type.value in ["finish", "error"] or len(steps) > 5:
                break
        
        execution_time = time.time() - start_time
        
        # Should complete within reasonable time (respecting timeouts)
        assert execution_time < 3.0  # Should not hang indefinitely
        
        # Should have at least attempted the operation
        assert len(steps) >= 1
    
    def test_race_condition_detection(self, stress_tools, stress_action_executor):
        """Test for race conditions in concurrent tool execution."""
        
        def race_condition_llm_chat(messages, tools):
            # Multiple calls to the racy tool without locks
            return ChatMessage(
                role=Role.ASSISTANT,
                content="Race condition test",
                tool_calls=[
                    ToolCall(
                        name="race_condition_tool",
                        args={"operation": "increment", "use_lock": False},
                        tool_call_id=f"race-{i}"
                    )
                    for i in range(5)  # 5 concurrent increments
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=race_condition_llm_chat,
            tools=stress_tools,
            parser=ToolCallParser(),
            max_steps=3
        )
        
        # Create execution handler using new pattern
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=stress_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Test race conditions")
        ]
        
        # Get the race condition tool to check its state
        racy_tool = next(tool for tool in stress_tools if tool.name == "race_condition_tool")
        initial_counter = racy_tool.shared_counter
        
        steps = []
        observations = []
        
        for step in iterator:
            steps.append(step)
            if step.type.value == "observation":
                observations.append(step.data)
            
            if step.type.value in ["finish", "error"] or len(steps) > 10:
                break
        
        final_counter = racy_tool.shared_counter
        
        # Should have executed multiple operations
        assert len(observations) >= 3
        
        # Counter should have increased (though maybe not by exactly 5 due to race conditions)
        assert final_counter > initial_counter
        
        # Due to race conditions, final counter might be less than initial + 5
        # This demonstrates the race condition behavior
        counter_increase = final_counter - initial_counter
        assert 1 <= counter_increase <= 5  # Some increments should succeed
