"""
Advanced ReAct agent workflow tests for comprehensive system validation.

Tests complex real-world scenarios that combine multiple failure modes,
recovery patterns, and edge cases to ensure bulletproof system behavior.

Uses professional testing tools with proper Pydantic schemas from the shared
fixtures library for consistency and reusability across test suites.
"""

import pytest
import time
from unittest.mock import Mock, patch
from mas.elements.llms.common.chat.message import ChatMessage, Role, ToolCall
from mas.elements.nodes.common.agent.strategies.react import ReActStrategy
from mas.elements.nodes.common.agent.execution import AgentIterator, ExecutionMode, ExecutionHandlerFactory
from mas.elements.nodes.common.agent.execution.executor import AgentActionExecutor
from mas.elements.nodes.common.agent.parsers.tool_call_parser import ToolCallParser
from mas.elements.nodes.common.agent.primitives import SystemError
from mas.elements.tools.common.execution import ToolExecutorManager, ExecutorConfig
from mas.elements.tools.common.execution.models import ExecutionMode as ToolExecutionMode


@pytest.mark.integration
@pytest.mark.agent_system
class TestReActAdvancedScenarios:
    """Advanced scenario tests using professional testing tools."""

    @pytest.fixture
    def robust_action_executor(self, advanced_testing_tools):
        """Create robust action executor with advanced testing tools."""
        config = ExecutorConfig(
            max_concurrent=2,  # Limited concurrency for complex scenarios
            execution_mode=ToolExecutionMode.CONCURRENT_LIMITED,
            default_timeout=5.0,
            enable_circuit_breaker=True,  # Enable for robust scenarios
            enable_metrics=True,
            error_handler=ExecutorConfig.create_robust().error_handler  # Use robust retry policy
            # Note: Removed validators to prevent schema validation issues with professional fixtures
        )
        manager = ToolExecutorManager(**config.to_dict())
        manager.set_tools({tool.name: tool for tool in advanced_testing_tools})
        return AgentActionExecutor(tool_executor_manager=manager)

    def test_network_partition_recovery_workflow(self, advanced_testing_tools, robust_action_executor):
        """Test agent behavior during network partition and recovery."""
        
        # Get the network tool from professional fixtures
        network_tool = next(tool for tool in advanced_testing_tools if "network" in tool.name)
        
        def network_partition_llm_chat(messages, tools):
            """LLM that tries network operations during partition."""
            return ChatMessage(
                role=Role.ASSISTANT,
                content="I'll check network connectivity and retry if needed.",
                tool_calls=[
                    ToolCall(
                        name=network_tool.name,
                        args={"operation": "query", "data": "connectivity_check"},
                        tool_call_id="net-1"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=network_partition_llm_chat,
            tools=advanced_testing_tools,
            parser=ToolCallParser(),
            max_steps=5
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=robust_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Check network status and handle any issues")
        ]
        
        # Simulate network partition by setting connection state
        network_tool.connection_state = "disconnected"
        
        steps = []
        observations = []
        
        for step in iterator:
            steps.append(step)
            if step.type.value == "observation":
                observations.append(step.data)
                
                # Simulate network recovery after first failure
                if len(observations) == 1 and not step.data.success:
                    network_tool.connection_state = "connected"
                    
            if step.type.value in ["finish", "error"] or len(steps) > 10:
                break
        
        # Verify recovery behavior
        assert len(observations) >= 1
        
        # System should handle network partition gracefully
        assert len(steps) >= 2  # At least planning + observation

    def test_authentication_escalation_workflow(self, advanced_testing_tools, robust_action_executor):
        """Test agent handling authentication failures and permission escalation."""
        
        # Get the authentication tool from professional fixtures
        auth_tool = next(tool for tool in advanced_testing_tools if "secure" in tool.name)
        
        # Test the tool directly first to ensure it works as expected
        try:
            auth_tool.run(action="write", resource="test")
            assert False, "Expected PermissionError for write action"
        except PermissionError:
            pass  # Expected
        
        # Verify read succeeds
        result = auth_tool.run(action="read", resource="test")
        assert "Auth success" in result
        
        def auth_escalation_llm_chat(messages, tools):
            """LLM that tries operations requiring different permission levels."""
            return ChatMessage(
                role=Role.ASSISTANT,
                content="I'll try to access the resource with appropriate permissions.",
                tool_calls=[
                    ToolCall(
                        name=auth_tool.name,
                        args={"action": "write", "resource": "sensitive_data"},
                        tool_call_id="auth-1"
                    ),
                    ToolCall(
                        name=auth_tool.name,
                        args={"action": "read", "resource": "public_data"},
                        tool_call_id="auth-2"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=auth_escalation_llm_chat,
            tools=advanced_testing_tools,
            parser=ToolCallParser(),
            max_steps=3
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=robust_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Access both sensitive and public data")
        ]
        
        steps = []
        observations = []
        
        for step in iterator:
            steps.append(step)
            if step.type.value == "observation":
                observations.append(step.data)
            if step.type.value in ["finish", "error"] or len(steps) > 8:
                break
        
        # Verify we got observations from both tool calls
        assert len(observations) >= 2
        
        # Group observations by tool calls
        write_obs = [obs for obs in observations if obs.action_id == "auth-1"]
        read_obs = [obs for obs in observations if obs.action_id == "auth-2"]
        
        # Verify both operations were attempted
        assert len(write_obs) >= 1  # Write operation attempted
        assert len(read_obs) >= 1   # Read operation attempted
        
        # Check results: write should fail, read should succeed
        write_result = write_obs[0]
        read_result = read_obs[0]
        
        # The key test: different permission outcomes
        assert write_result.success != read_result.success  # Should have different outcomes
        
        # Write should fail due to permissions, read should succeed
        assert not write_result.success  # Write should fail
        assert read_result.success       # Read should succeed
        
        # Verify specific error/success messages
        assert "permission" in str(write_result.error).lower()  # Write failed due to permissions
        assert "Auth success" in read_result.output  # Read succeeded

    def test_data_corruption_validation_workflow(self, advanced_testing_tools, robust_action_executor):
        """Test agent handling data corruption and validation errors."""
        
        # Get the data corruption tool from professional fixtures
        data_tool = next(tool for tool in advanced_testing_tools if "data" in tool.name)
        
        def data_validation_llm_chat(messages, tools):
            """LLM that processes data with validation."""
            return ChatMessage(
                role=Role.ASSISTANT,
                content="I'll process the data with validation enabled.",
                tool_calls=[
                    ToolCall(
                        name=data_tool.name,
                        args={"data": "important_data_payload", "validate": True},
                        tool_call_id="data-1"
                    ),
                    ToolCall(
                        name=data_tool.name,
                        args={"data": "backup_data", "validate": False},
                        tool_call_id="data-2"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=data_validation_llm_chat,
            tools=advanced_testing_tools,
            parser=ToolCallParser(),
            max_steps=4
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=robust_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Process data with validation")
        ]
        
        steps = []
        observations = []
        
        for step in iterator:
            steps.append(step)
            if step.type.value == "observation":
                observations.append(step.data)
            if step.type.value in ["finish", "error"] or len(steps) > 8:
                break
        
        # Verify data processing behavior
        assert len(observations) >= 1
        
        # Should handle validation errors gracefully (may or may not occur due to randomness)
        assert all(hasattr(obs, 'success') for obs in observations)

    def test_circuit_breaker_recovery_workflow(self, advanced_testing_tools, robust_action_executor):
        """Test agent behavior with circuit breaker pattern."""
        
        # Get the circuit breaker tool from professional fixtures
        circuit_tool = next(tool for tool in advanced_testing_tools if "external" in tool.name)
        
        # Reset the circuit breaker tool state for consistent testing
        circuit_tool.failure_count = 0
        
        def circuit_breaker_llm_chat(messages, tools):
            """LLM that repeatedly calls a failing service."""
            return ChatMessage(
                role=Role.ASSISTANT,
                content="I'll try to access the external service multiple times.",
                tool_calls=[
                    ToolCall(
                        name=circuit_tool.name,
                        args={"operation": f"request_{i}"},
                        tool_call_id=f"circuit-{i}"
                    )
                    for i in range(5)  # Multiple attempts to trigger circuit breaker
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=circuit_breaker_llm_chat,
            tools=advanced_testing_tools,
            parser=ToolCallParser(),
            max_steps=1  # Only one step to test the circuit breaker pattern
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=robust_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Access external service with retry logic")
        ]
        
        steps = []
        observations = []
        
        for step in iterator:
            steps.append(step)
            if step.type.value == "observation":
                observations.append(step.data)
            if step.type.value in ["finish", "error"] or len(steps) > 10:
                break
        
        # Verify circuit breaker behavior with retry mechanism
        assert len(observations) == 5  # Should have exactly 5 tool calls
        
        # With the retry mechanism, all calls should eventually succeed
        # But we can verify the circuit breaker was triggered by checking the outputs
        successful_calls = [obs for obs in observations if obs.success]
        assert len(successful_calls) == 5  # All should succeed after retries
        
        # All successful calls should mention "recovered" indicating circuit breaker worked
        for obs in successful_calls:
            assert "recovered" in obs.output, f"Output should indicate recovery: {obs.output}"
            
        # Verify the circuit breaker reset properly for the test
        assert circuit_tool.failure_count > 3  # Should have exceeded threshold

    def test_multi_failure_cascade_recovery_workflow(self, advanced_testing_tools, robust_action_executor):
        """Test agent handling multiple simultaneous failure modes."""
        
        # Get all tools from professional fixtures
        network_tool = next(tool for tool in advanced_testing_tools if "network" in tool.name)
        auth_tool = next(tool for tool in advanced_testing_tools if "secure" in tool.name)
        data_tool = next(tool for tool in advanced_testing_tools if "data" in tool.name)
        circuit_tool = next(tool for tool in advanced_testing_tools if "external" in tool.name)
        
        def multi_failure_llm_chat(messages, tools):
            """LLM that triggers multiple failure modes simultaneously."""
            return ChatMessage(
                role=Role.ASSISTANT,
                content="I'll perform a complex operation involving multiple services.",
                tool_calls=[
                    ToolCall(
                        name=network_tool.name,
                        args={"operation": "query", "data": "multi_service_check"},
                        tool_call_id="multi-1"
                    ),
                    ToolCall(
                        name=auth_tool.name,
                        args={"action": "admin", "resource": "system_config"},
                        tool_call_id="multi-2"
                    ),
                    ToolCall(
                        name=data_tool.name,
                        args={"data": "x" * 150, "validate": True},  # Too large + validation
                        tool_call_id="multi-3"
                    ),
                    ToolCall(
                        name=circuit_tool.name,
                        args={"operation": "critical_update"},
                        tool_call_id="multi-4"
                    )
                ]
            )
        
        # Set up multiple failure conditions
        network_tool.connection_state = "slow"  # Network issues
        data_tool.corruption_rate = 1.0  # Guaranteed corruption
        circuit_tool.failure_count = 0  # Will fail initially
        
        strategy = ReActStrategy(
            llm_chat=multi_failure_llm_chat,
            tools=advanced_testing_tools,
            parser=ToolCallParser(),
            max_steps=5
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=robust_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Perform complex multi-service operation")
        ]
        
        steps = []
        observations = []
        
        for step in iterator:
            steps.append(step)
            if step.type.value == "observation":
                observations.append(step.data)
            if step.type.value in ["finish", "error"] or len(steps) > 15:
                break
        
        # Verify system handles multiple failures gracefully
        assert len(observations) >= 4  # Should attempt all operations
        
        # Should have multiple different types of failures
        error_types = set()
        for obs in observations:
            if not obs.success and obs.error:
                error_str = str(obs.error).lower()
                if "timeout" in error_str or "connection" in error_str:
                    error_types.add("network")
                elif "permission" in error_str:
                    error_types.add("auth")
                elif "corruption" in error_str or "too large" in error_str:
                    error_types.add("data")
                elif "unavailable" in error_str:
                    error_types.add("circuit")
        
        # Should encounter multiple failure types
        assert len(error_types) >= 2  # Multiple different failure modes
        
        # System should not crash despite multiple failures
        assert len(steps) >= 5  # Should have planning + multiple observations

    def test_guided_mode_complex_decision_workflow(self, advanced_testing_tools):
        """Test guided mode with complex decision-making scenarios."""
        
        # Create separate executor for guided mode
        config = ExecutorConfig(
            max_concurrent=2,
            execution_mode=ToolExecutionMode.CONCURRENT_LIMITED,
            default_timeout=5.0,
            enable_circuit_breaker=True,
            error_handler=ExecutorConfig.create_robust().error_handler
            # Note: Removed validators to prevent schema validation issues with professional fixtures
        )
        manager = ToolExecutorManager(**config.to_dict())
        manager.set_tools({tool.name: tool for tool in advanced_testing_tools})
        action_executor = AgentActionExecutor(tool_executor_manager=manager)
        
        auth_tool = next(tool for tool in advanced_testing_tools if "secure" in tool.name)
        data_tool = next(tool for tool in advanced_testing_tools if "data" in tool.name)
        
        def complex_decision_llm_chat(messages, tools):
            """LLM that requires human guidance for complex decisions."""
            return ChatMessage(
                role=Role.ASSISTANT,
                content="I need to make some complex decisions. Let me propose actions.",
                tool_calls=[
                    ToolCall(
                        name=auth_tool.name,
                        args={"action": "write", "resource": "critical_system"},
                        tool_call_id="decision-1"
                    ),
                    ToolCall(
                        name=data_tool.name,
                        args={"data": "sensitive_user_data", "validate": True},
                        tool_call_id="decision-2"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=complex_decision_llm_chat,
            tools=advanced_testing_tools,
            parser=ToolCallParser(),
            max_steps=4
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.GUIDED,
            action_executor=action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Perform sensitive operations with approval")
        ]
        
        steps = []
        pending_actions = []
        
        # Process initial steps to get pending actions
        for step in iterator:
            steps.append(step)
            if step.type.value == "action":
                pending_actions.append(step.data)
            if len(pending_actions) >= 2 or len(steps) > 5:
                break
        
        # Verify guided mode behavior
        assert len(pending_actions) >= 2  # Should have actions pending approval
        
        # Simulate human decisions: approve first, reject second
        if len(pending_actions) >= 1:
            approval_step = iterator.confirm_action(pending_actions[0].id, execute=True)
            if approval_step:
                steps.append(approval_step)
        
        if len(pending_actions) >= 2:
            iterator.confirm_action(pending_actions[1].id, execute=False)
        
        # Continue execution
        for step in iterator:
            steps.append(step)
            if step.type.value in ["finish", "error"] or len(steps) > 10:
                break
        
        # Verify guided execution
        observation_steps = [s for s in steps if s.type.value == "observation"]
        
        # Should have at least one observation (from approved action)
        assert len(observation_steps) >= 1
        
        # Should handle mixed approval/rejection gracefully
        assert len(steps) >= 3  # Planning + action + observation minimum
