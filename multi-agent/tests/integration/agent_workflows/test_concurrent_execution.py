"""
Comprehensive concurrent execution testing for the multi-agent system.

This module tests advanced concurrent execution patterns, resource contention,
semaphore behavior, and performance characteristics under various loads.
"""

import pytest
import time
import threading
from unittest.mock import Mock

from mas.elements.llms.common.chat.message import ChatMessage, Role, ToolCall
from mas.elements.nodes.common.agent.parsers import ToolCallParser
from mas.elements.nodes.common.agent.strategies.react import ReActStrategy
from mas.elements.nodes.common.agent.execution import AgentIterator, ExecutionMode, ExecutionHandlerFactory
from mas.elements.nodes.common.agent.execution.executor import AgentActionExecutor
from mas.elements.tools.common.execution import ToolExecutorManager, ExecutorConfig
from mas.elements.tools.common.execution.models import ExecutionMode as ToolExecutionMode


@pytest.fixture
def concurrent_action_executor(comprehensive_concurrent_tools):
    """Action executor configured for concurrent testing."""
    config = ExecutorConfig(
        max_concurrent=3,  # Strict limit for testing
        execution_mode=ToolExecutionMode.CONCURRENT_LIMITED,  # Use concurrent limited for testing
        default_timeout=5.0,
        enable_circuit_breaker=False,  # Disable for cleaner test results
        enable_metrics=True
    )
    manager = ToolExecutorManager(**config.to_dict())
    
    # Register all concurrent testing tools
    all_tools = comprehensive_concurrent_tools['all_tools']
    manager.set_tools({tool.name: tool for tool in all_tools})
    
    return AgentActionExecutor(tool_executor_manager=manager)


class TestConcurrentExecution:
    """Comprehensive concurrent execution tests."""

    def test_semaphore_respects_max_concurrent_limit(self, semaphore_testing_tools):
        """
        Test that semaphore strictly enforces max_concurrent limit.
        
        This test verifies that exactly max_concurrent tools run simultaneously,
        never exceeding the limit even under high load.
        """
        tools_data = semaphore_testing_tools
        tools = tools_data['tools']
        tracker = tools_data['tracker']
        
        # Reset tracker for clean test
        tracker.reset()
        
        # Create dedicated executor with semaphore tools
        config = ExecutorConfig(
            max_concurrent=3,  # This is what we're testing!
            execution_mode=ToolExecutionMode.CONCURRENT_LIMITED,
            default_timeout=5.0,
            enable_circuit_breaker=False,
            enable_metrics=True
        )
        manager = ToolExecutorManager(**config.to_dict())
        manager.set_tools({tool.name: tool for tool in tools})  # Register the semaphore tools
        semaphore_executor = AgentActionExecutor(tool_executor_manager=manager)
        
        def semaphore_test_llm_chat(messages, tools):
            """LLM that requests many concurrent operations."""
            return ChatMessage(
                role=Role.ASSISTANT,
                content="I'll test the semaphore limits with many concurrent operations.",
                tool_calls=[
                    ToolCall(
                        name=f"semaphore_test_{i}",
                        args={"operation": "semaphore_test", "duration": 0.2, "tool_id": f"test_{i}"},
                        tool_call_id=f"semaphore-{i}"
                    )
                    for i in range(10)  # Request 10 tools (> max_concurrent=3)
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=semaphore_test_llm_chat,
            tools=tools,
            parser=ToolCallParser(),
            max_steps=1  # Single step for focused testing
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=semaphore_executor  # Use the dedicated semaphore executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Test semaphore with 10 concurrent tools")
        ]
        
        # Execute and collect results
        start_time = time.time()
        observations = []
        
        for step in iterator:
            if step.type.value == "observation":
                observations.append(step.data)
            if step.type.value in ["finish", "error"] or len(observations) >= 10:
                break
        
        execution_time = time.time() - start_time
        
        # Verify semaphore behavior
        max_concurrent = tracker.get_max_concurrent()
        execution_log = tracker.get_execution_log()
        
        # CRITICAL: Should never exceed max_concurrent=3
        assert max_concurrent <= 3, f"Exceeded max_concurrent limit: {max_concurrent} > 3"
        
        # Should actually use the full limit (efficient)
        assert max_concurrent >= 2, f"Underutilized concurrency: {max_concurrent} < 2"
        
        # All tools should complete
        assert len(observations) == 10, f"Not all tools completed: {len(observations)} != 10"
        
        # Should be faster than sequential (10 * 0.2s = 2s)
        # With max_concurrent=3, should take ~(10/3 * 0.2s) = ~0.67s + overhead
        assert execution_time < 1.5, f"Too slow for concurrent execution: {execution_time}s"
        
        print(f"✅ Semaphore test: max_concurrent={max_concurrent}, time={execution_time:.3f}s")

    def test_strategy_performance_comparison(self, timing_test_tools, concurrent_action_executor):
        """
        Test performance differences between execution strategies.
        
        This test uses a scenario designed to show clear differences:
        - 10 tools, each taking 0.5s 
        - max_concurrent=2 for limited strategy
        - This creates a clear bottleneck that demonstrates the differences
        """

        # Test different execution strategies with more pronounced differences
        configs = {
            'sequential': ExecutorConfig(
                execution_mode=ToolExecutionMode.SEQUENTIAL,
                max_concurrent=1,
                enable_circuit_breaker=False,
                default_timeout=10.0
            ),
            'parallel': ExecutorConfig(
                execution_mode=ToolExecutionMode.PARALLEL,
                max_concurrent=100,
                enable_circuit_breaker=False,
                default_timeout=10.0
            ),
            'limited': ExecutorConfig(
                execution_mode=ToolExecutionMode.CONCURRENT_LIMITED,
                max_concurrent=2,  # Very limited to create clear bottleneck
                enable_circuit_breaker=False,
                default_timeout=10.0
            )
        }

        results = {}

        for strategy_name, config in configs.items():
            manager = ToolExecutorManager(**config.to_dict())
            # Register timing test tools
            manager.set_tools({tool.name: tool for tool in timing_test_tools})
            executor = AgentActionExecutor(tool_executor_manager=manager)

            def timing_test_llm_chat(messages, tools):
                # Create 10 tool calls, each taking 0.5s to create clear timing differences
                tool_calls = []
                for i in range(10):
                    tool_calls.append(ToolCall(
                        name="timing_cpu",
                        args={"duration": 0.5, "work_type": "cpu"},
                        tool_call_id=f"{strategy_name}-tool-{i+1}"
                    ))
                
                return ChatMessage(
                    role=Role.ASSISTANT,
                    content=f"Testing {strategy_name} execution strategy with 10 tools of 0.5s each.",
                    tool_calls=tool_calls
                )

            strategy = ReActStrategy(
                llm_chat=timing_test_llm_chat,
                tools=timing_test_tools,
                parser=ToolCallParser(),
                max_steps=1
            )

            execution_handler = ExecutionHandlerFactory.create(
                mode=ExecutionMode.AUTO,
                action_executor=executor
            )

            iterator = AgentIterator(
                strategy=strategy,
                execution_handler=execution_handler
            )

            iterator.messages = [
                ChatMessage(role=Role.USER, content=f"Test {strategy_name} strategy")
            ]

            # Measure execution time
            start_time = time.time()
            observations = []

            for step in iterator:
                if step.type.value == "observation":
                    observations.append(step.data)
                if step.type.value in ["finish", "error"] or len(observations) >= 10:
                    break

            execution_time = time.time() - start_time
            results[strategy_name] = {
                'time': execution_time,
                'observations': len(observations)
            }

            print(f"Strategy {strategy_name}: {execution_time:.3f}s, {len(observations)} observations")

        # Verify performance characteristics with 10 tools @ 0.5s each
        sequential_time = results['sequential']['time']
        parallel_time = results['parallel']['time']
        limited_time = results['limited']['time']

        # Expected times:
        # Sequential: 10 × 0.5s = 5.0s
        # Parallel: ~0.5s + overhead (all at once)
        # Limited (max_concurrent=2): ~2.5s (pipelined execution)

        # Core test purpose: Verify strategies execute in the expected performance order
        # Sequential should be slowest
        assert sequential_time > parallel_time, f"Sequential not slower than parallel: {sequential_time:.3f} <= {parallel_time:.3f}"
        assert sequential_time > limited_time, f"Sequential not slower than limited: {sequential_time:.3f} <= {limited_time:.3f}"

        # Parallel should be fastest
        assert parallel_time < limited_time, f"Parallel not faster than limited: {parallel_time:.3f} >= {limited_time:.3f}"
        
        # Verify strategies show meaningful performance differences (not just ordering)
        # Sequential should be substantially slower than both others (at least 2x)
        assert sequential_time > parallel_time * 2.0, f"Sequential not substantially slower than parallel: {sequential_time:.3f} <= {parallel_time * 2.0:.3f}"
        assert sequential_time > limited_time * 1.5, f"Sequential not substantially slower than limited: {sequential_time:.3f} <= {limited_time * 1.5:.3f}"
        
        # Limited should show some bottleneck effect compared to parallel (at least 30% slower)
        # This is a generous threshold that focuses on detecting the bottleneck rather than exact ratios
        assert limited_time > parallel_time * 1.3, f"Limited shows no meaningful bottleneck vs parallel: {limited_time:.3f} <= {parallel_time * 1.3:.3f}"
        
        # Verify all strategies completed successfully
        for strategy_name, result in results.items():
            assert result['observations'] == 10, f"Strategy {strategy_name} should complete all 10 observations, got {result['observations']}"
        
        # Verify reasonable timing ranges (generous bounds to focus on behavior, not exact timing)
        assert sequential_time > 3.0, f"Sequential suspiciously fast: {sequential_time:.3f}s < 3.0s"    # Should be much slower
        assert parallel_time < 2.0, f"Parallel suspiciously slow: {parallel_time:.3f}s >= 2.0s"        # Should be much faster
        assert limited_time < 4.0, f"Limited suspiciously slow: {limited_time:.3f}s >= 4.0s"           # Should be faster than sequential
        
        print(f"✅ Strategy comparison: Sequential={sequential_time:.3f}s, Parallel={parallel_time:.3f}s, Limited={limited_time:.3f}s")

    def test_parallel_execution_proof(self, timing_test_tools):
        """
        Definitive proof that parallel execution works by testing execution overlap.
        
        This test uses long-running tools (1 second each) to clearly demonstrate
        that parallel execution has significant time savings vs sequential.
        """
        import time
        
        # Create executor with parallel mode
        config = ExecutorConfig(
            execution_mode=ToolExecutionMode.PARALLEL,
            max_concurrent=100,
            enable_circuit_breaker=False,
            default_timeout=10.0
        )
        manager = ToolExecutorManager(**config.to_dict())
        manager.set_tools({tool.name: tool for tool in timing_test_tools})
        parallel_executor = AgentActionExecutor(tool_executor_manager=manager)

        def parallel_proof_llm_chat(messages, tools):
            """LLM that requests 3 long-running tools that MUST overlap to finish quickly."""
            return ChatMessage(
                role=Role.ASSISTANT,
                content="Testing TRUE parallel execution with 1-second tools.",
                tool_calls=[
                    ToolCall(
                        name="timing_cpu",
                        args={"duration": 1.0, "work_type": "cpu"},
                        tool_call_id="proof-cpu"
                    ),
                    ToolCall(
                        name="timing_io", 
                        args={"duration": 1.0, "work_type": "io"},
                        tool_call_id="proof-io"
                    ),
                    ToolCall(
                        name="timing_mixed",
                        args={"duration": 1.0, "work_type": "mixed"}, 
                        tool_call_id="proof-mixed"
                    )
                ]
            )

        strategy = ReActStrategy(
            llm_chat=parallel_proof_llm_chat,
            tools=timing_test_tools,
            parser=ToolCallParser(),
            max_steps=1
        )

        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=parallel_executor
        )

        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )

        iterator.messages = [
            ChatMessage(role=Role.USER, content="Prove parallel execution")
        ]

        # CRITICAL TEST: If parallel works, 3×1s tools should complete in ~1s, not 3s
        start_time = time.time()
        observations = []

        for step in iterator:
            if step.type.value == "observation":
                observations.append(step.data)
            if step.type.value in ["finish", "error"] or len(observations) >= 3:
                break

        execution_time = time.time() - start_time

        print(f"🎯 PARALLEL PROOF: {len(observations)} tools × 1.0s each completed in {execution_time:.3f}s")
        
        # DEFINITIVE PROOF: Must complete in < 1.5s to prove overlap (not 3s sequential)
        assert execution_time < 1.5, f"PARALLEL FAILED: {execution_time:.3f}s >= 1.5s (expected ~1.0s if truly parallel)"
        assert execution_time > 0.8, f"TOOLS TOO FAST: {execution_time:.3f}s < 0.8s (tools may not be working)"
        assert len(observations) == 3, f"MISSING TOOLS: {len(observations)} != 3"
        
        # Calculate parallel efficiency 
        theoretical_sequential = 3.0  # 3 × 1.0s
        parallel_speedup = theoretical_sequential / execution_time
        
        print(f"🚀 PARALLEL EFFICIENCY: {parallel_speedup:.1f}x speedup (3×1s tools in {execution_time:.3f}s)")
        
        # Must achieve at least 2x speedup to prove meaningful parallelism
        assert parallel_speedup >= 2.0, f"INSUFFICIENT PARALLELISM: {parallel_speedup:.1f}x < 2.0x speedup"

    def test_concurrent_limited_proof(self, timing_test_tools):
        """
        Definitive proof that concurrent limited execution respects semaphore limits.
        
        Uses 5 tools with max_concurrent=2 to prove only 2 run at once.
        """
        import time
        
        # Create executor with limited concurrency
        config = ExecutorConfig(
            execution_mode=ToolExecutionMode.CONCURRENT_LIMITED,
            max_concurrent=2,  # KEY: Only 2 tools can run simultaneously
            enable_circuit_breaker=False,
            default_timeout=15.0
        )
        manager = ToolExecutorManager(**config.to_dict())
        manager.set_tools({tool.name: tool for tool in timing_test_tools})
        limited_executor = AgentActionExecutor(tool_executor_manager=manager)

        def limited_proof_llm_chat(messages, tools):
            """LLM that requests 5 tools that must respect concurrency limit."""
            return ChatMessage(
                role=Role.ASSISTANT,
                content="Testing concurrent limited execution with max_concurrent=2.",
                tool_calls=[
                    ToolCall(name="timing_cpu", args={"duration": 1.0, "work_type": "cpu"}, tool_call_id="limit-1"),
                    ToolCall(name="timing_io", args={"duration": 1.0, "work_type": "io"}, tool_call_id="limit-2"), 
                    ToolCall(name="timing_mixed", args={"duration": 1.0, "work_type": "mixed"}, tool_call_id="limit-3"),
                    ToolCall(name="timing_cpu", args={"duration": 1.0, "work_type": "cpu"}, tool_call_id="limit-4"),
                    ToolCall(name="timing_io", args={"duration": 1.0, "work_type": "io"}, tool_call_id="limit-5")
                ]
            )

        strategy = ReActStrategy(
            llm_chat=limited_proof_llm_chat,
            tools=timing_test_tools,
            parser=ToolCallParser(),
            max_steps=1
        )

        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=limited_executor
        )

        iterator = AgentIterator(strategy=strategy, execution_handler=execution_handler)
        iterator.messages = [ChatMessage(role=Role.USER, content="Prove concurrent limited execution")]

        # CRITICAL TEST: 5 tools with max_concurrent=2 should take ~3s (3 batches: 2+2+1)
        start_time = time.time()
        observations = []

        for step in iterator:
            if step.type.value == "observation":
                observations.append(step.data)
            if step.type.value in ["finish", "error"] or len(observations) >= 5:
                break

        execution_time = time.time() - start_time

        print(f"🎯 CONCURRENT LIMITED PROOF: 5 tools (max_concurrent=2) completed in {execution_time:.3f}s")
        
        # PROOF: Must take 2.5-4s to prove semaphore limiting (not ~1s like full parallel)
        assert execution_time > 2.5, f"TOO FAST: {execution_time:.3f}s < 2.5s (may not be limiting concurrency)"
        assert execution_time < 4.0, f"TOO SLOW: {execution_time:.3f}s >= 4.0s (may not be using concurrency)"
        assert len(observations) == 5, f"MISSING TOOLS: {len(observations)} != 5"
        
        # Calculate batching efficiency
        theoretical_batches = 3  # ceil(5 tools / 2 max_concurrent) = 3 batches
        expected_time = theoretical_batches * 1.0  # 3s
        efficiency = expected_time / execution_time
        
        print(f"🔒 SEMAPHORE EFFICIENCY: {efficiency:.1f}x (expected ~3s for 3 batches, got {execution_time:.3f}s)")
        
        # Should be reasonably close to theoretical batching time
        assert efficiency > 0.7, f"POOR BATCHING: {efficiency:.1f}x < 0.7x efficiency"

    def test_resource_contention_direct(self, resource_contention_tools):
        """Direct test of resource contention tools without agent system."""
        tools_data = resource_contention_tools
        tools = tools_data['tools']
        counter = tools_data['counter']
        
        # Reset shared resources
        counter.reset()
        
        print(f"🔍 DIRECT TEST: Initial counter value: {counter.get_value()}")
        print(f"🔍 DIRECT TEST: Counter ID: {id(counter)}")
        print(f"🔍 DIRECT TEST: Tool counter IDs: {[id(tool.counter) for tool in tools]}")
        
        # Test tools directly
        result1 = tools[0].run('increment', duration=0.0)
        print(f"🔍 DIRECT TEST: Tool 0 result: {result1}")
        print(f"🔍 DIRECT TEST: Counter value after tool 0: {counter.get_value()}")
        
        result2 = tools[1].run('increment', duration=0.0)
        print(f"🔍 DIRECT TEST: Tool 1 result: {result2}")
        print(f"🔍 DIRECT TEST: Counter value after tool 1: {counter.get_value()}")
        
        result3 = tools[2].run('increment', duration=0.0)
        print(f"🔍 DIRECT TEST: Tool 2 result: {result3}")
        print(f"🔍 DIRECT TEST: Counter value after tool 2: {counter.get_value()}")
        
        # Verify the tools work correctly
        assert counter.get_value() == 3, f"Direct test failed: {counter.get_value()} != 3"
        assert len(counter.get_access_log()) == 3, f"Direct test log failed: {len(counter.get_access_log())} != 3"
        
    def test_shared_resource_contention(self, resource_contention_tools):
        """
        Test concurrent access to shared resources.
        
        Verifies that shared resources (files, counters) are accessed
        safely under concurrent load without corruption or race conditions.
        """
        tools_data = resource_contention_tools
        tools = tools_data['tools']
        counter = tools_data['counter']
        file_resource = tools_data['file_resource']
        
        # Reset shared resources
        counter.reset()
        
        # Create dedicated executor with resource contention tools
        config = ExecutorConfig(
            max_concurrent=3,
            execution_mode=ToolExecutionMode.CONCURRENT_LIMITED,
            default_timeout=5.0,
            enable_circuit_breaker=False,
            enable_metrics=True
        )
        manager = ToolExecutorManager(**config.to_dict())
        manager.set_tools({tool.name: tool for tool in tools})  # Register the resource tools
        resource_executor = AgentActionExecutor(tool_executor_manager=manager)
        
        def resource_contention_llm_chat(messages, tools):
            """LLM that accesses shared resources concurrently."""
            return ChatMessage(
                role=Role.ASSISTANT,
                content="I'll access shared resources concurrently to test thread safety.",
                tool_calls=[
                    # Multiple counter increments
                    ToolCall(
                        name="resource_tool_0",
                        args={"operation": "increment", "duration": 0.1},
                        tool_call_id="increment-1"
                    ),
                    ToolCall(
                        name="resource_tool_1", 
                        args={"operation": "increment", "duration": 0.1},
                        tool_call_id="increment-2"
                    ),
                    ToolCall(
                        name="resource_tool_2",
                        args={"operation": "increment", "duration": 0.1},
                        tool_call_id="increment-3"
                    ),
                    # Concurrent file writes
                    ToolCall(
                        name="resource_tool_0",
                        args={"operation": "write", "data": "concurrent_data_1", "duration": 0.1},
                        tool_call_id="write-1"
                    ),
                    ToolCall(
                        name="resource_tool_1",
                        args={"operation": "write", "data": "concurrent_data_2", "duration": 0.1},
                        tool_call_id="write-2"
                    ),
                    # File read operations
                    ToolCall(
                        name="resource_tool_2",
                        args={"operation": "read", "duration": 0.1},
                        tool_call_id="read-1"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=resource_contention_llm_chat,
            tools=tools,
            parser=ToolCallParser(),
            max_steps=1
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=resource_executor  # Use the dedicated resource executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Test shared resource access")
        ]
        
        # Execute concurrent operations
        observations = []

        for step in iterator:
            if step.type.value == "observation":
                observations.append(step.data)
                # Debug: Print observation details
                print(f"🔍 OBSERVATION: tool={step.data.tool}, success={step.data.success}, output='{step.data.output}'")
            if step.type.value in ["finish", "error"] or len(observations) >= 6:
                break
        
        # Verify shared resource integrity
        final_counter_value = counter.get_value()
        counter_access_log = counter.get_access_log()
        file_access_log = file_resource.get_access_log()
        
        # Debug: Print resource state
        print(f"🔍 COUNTER: final_value={final_counter_value}, access_log_entries={len(counter_access_log)}")
        print(f"🔍 COUNTER ID: {id(counter)}")
        print(f"🔍 TOOLS COUNTER IDs: {[id(tool.counter) for tool in tools]}")
        if counter_access_log:
            print(f"🔍 ACCESS LOG: {counter_access_log}")
        if file_access_log:
            print(f"🔍 FILE LOG: {file_access_log}")
        
        # Counter should have exactly 3 increments
        assert final_counter_value == 3, f"Counter corruption: expected 3, got {final_counter_value}"
        
        # Should have 3 increment operations logged (total access log entries)
        assert len(counter_access_log) == 3, f"Missing increment operations: {len(counter_access_log)} != 3"
        
        # Should have 2 write + 1 read file operations
        write_ops = [log for log in file_access_log if log['operation'] == 'write']
        read_ops = [log for log in file_access_log if log['operation'] == 'read']
        assert len(write_ops) == 2, f"Missing write operations: {len(write_ops)} != 2"
        assert len(read_ops) == 1, f"Missing read operations: {len(read_ops)} != 1"
        
        # All operations should complete successfully
        successful_ops = [obs for obs in observations if obs.success]
        assert len(successful_ops) == 6, f"Failed operations: {len(successful_ops)} != 6"
        
        print(f"✅ Resource contention test: counter={final_counter_value}, writes={len(write_ops)}, reads={len(read_ops)}")

    def test_mixed_duration_concurrent_execution(self, timing_test_tools, concurrent_action_executor):
        """
        Test concurrent execution with mixed tool durations.
        
        Verifies that fast tools don't wait for slow tools and that
        concurrency provides benefits with mixed workloads.
        """
        def mixed_duration_llm_chat(messages, tools):
            """LLM with mixed fast and slow operations."""
            return ChatMessage(
                role=Role.ASSISTANT,
                content="I'll execute tools with mixed durations concurrently.",
                tool_calls=[
                    # Fast tools (should complete quickly)
                    ToolCall(
                        name="timing_cpu",
                        args={"duration": 0.1, "work_type": "cpu"},
                        tool_call_id="fast-1"
                    ),
                    ToolCall(
                        name="timing_io",
                        args={"duration": 0.1, "work_type": "io"},
                        tool_call_id="fast-2"
                    ),
                    # Slow tools (should not block fast tools)
                    ToolCall(
                        name="timing_mixed",
                        args={"duration": 1.0, "work_type": "mixed"},
                        tool_call_id="slow-1"
                    ),
                    ToolCall(
                        name="timing_cpu",
                        args={"duration": 1.2, "work_type": "cpu"},
                        tool_call_id="slow-2"
                    ),
                    # Medium tools
                    ToolCall(
                        name="timing_io",
                        args={"duration": 0.5, "work_type": "io"},
                        tool_call_id="medium-1"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=mixed_duration_llm_chat,
            tools=timing_test_tools,
            parser=ToolCallParser(),
            max_steps=1
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=concurrent_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Test mixed duration execution")
        ]
        
        # Track completion times
        completion_times = {}
        start_time = time.time()
        observations = []
        
        for step in iterator:
            if step.type.value == "observation":
                obs = step.data
                observations.append(obs)
                completion_time = time.time() - start_time
                completion_times[obs.action_id] = completion_time
            if step.type.value in ["finish", "error"] or len(observations) >= 5:
                break
        
        total_time = time.time() - start_time
        
        # Verify mixed duration behavior
        fast_completions = [completion_times[obs.action_id] for obs in observations 
                          if obs.action_id in ["fast-1", "fast-2"]]
        slow_completions = [completion_times[obs.action_id] for obs in observations 
                          if obs.action_id in ["slow-1", "slow-2"]]
        
        # Fast tools should complete much faster than slow tools
        if fast_completions and slow_completions:
            avg_fast = sum(fast_completions) / len(fast_completions)
            avg_slow = sum(slow_completions) / len(slow_completions)
            assert avg_fast < avg_slow, f"Fast tools not faster: {avg_fast:.3f}s >= {avg_slow:.3f}s"
        
        # Total time should be less than sequential (0.1+0.1+1.0+1.2+0.5 = 2.9s)
        assert total_time < 2.5, f"Not faster than sequential: {total_time:.3f}s >= 2.5s"
        
        # All tools should complete
        assert len(observations) == 5, f"Not all tools completed: {len(observations)} != 5"
        
        print(f"✅ Mixed duration test: total_time={total_time:.3f}s, fast_avg={sum(fast_completions)/len(fast_completions) if fast_completions else 0:.3f}s")

    def test_high_concurrency_backpressure(self, semaphore_testing_tools, concurrent_action_executor):
        """
        Test system behavior under high concurrency load.
        
        Verifies that the system handles backpressure correctly when
        tool requests exceed available concurrency slots.
        """
        tools_data = semaphore_testing_tools
        tools = tools_data['tools']
        tracker = tools_data['tracker']
        
        # Reset tracker
        tracker.reset()
        
        def high_load_llm_chat(messages, tools):
            """LLM that requests many more tools than max_concurrent."""
            return ChatMessage(
                role=Role.ASSISTANT,
                content="Testing high concurrency load with backpressure.",
                tool_calls=[
                    ToolCall(
                        name=f"semaphore_test_{i % len(tools)}",
                        args={"operation": "backpressure_test", "duration": 0.1, "tool_id": f"load_{i}"},
                        tool_call_id=f"load-{i}"
                    )
                    for i in range(10)  # Request 10 tools (max allowed) with max_concurrent=3
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=high_load_llm_chat,
            tools=tools,
            parser=ToolCallParser(),
            max_steps=1
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=concurrent_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Test high concurrency load")
        ]
        
        # Execute under high load
        start_time = time.time()
        observations = []
        
        for step in iterator:
            if step.type.value == "observation":
                observations.append(step.data)
            if step.type.value in ["finish", "error"] or len(observations) >= 10:
                break
        
        execution_time = time.time() - start_time
        
        # Verify backpressure handling
        max_concurrent = tracker.get_max_concurrent()
        execution_log = tracker.get_execution_log()
        
        # Should respect concurrency limit even under high load
        assert max_concurrent <= 3, f"Exceeded limit under load: {max_concurrent} > 3"
        
        # All tools should eventually complete (no lost requests)
        assert len(observations) == 10, f"Lost requests under load: {len(observations)} != 10"
        
        # Should be efficient (batching helps with throughput)
        # With max_concurrent=3 and 0.1s per tool: 10 tools should take ~(10/3 * 0.1) = 0.33s + overhead
        assert execution_time < 1.0, f"Poor throughput under load: {execution_time:.3f}s >= 1.0s"
        
        print(f"✅ High load test: {len(observations)} tools, max_concurrent={max_concurrent}, time={execution_time:.3f}s")

    def test_error_propagation_in_concurrent_execution(self, timing_test_tools):
        """
        Test how errors propagate during concurrent execution.
        
        Verifies that errors in some tools don't prevent other
        concurrent tools from completing successfully.
        """
        # Create a mix of good and bad tools
        good_tools = timing_test_tools
        
        # Create a failing tool
        class FailingTool:
            name = "failing_tool"
            description = "Tool that always fails"
            
            def run(self, *args, **kwargs):
                raise RuntimeError("Intentional test failure")
        
        failing_tool = FailingTool()
        mixed_tools = good_tools + [failing_tool]
        
        # Create executor with mixed tools
        config = ExecutorConfig(
            max_concurrent=3,
            execution_mode=ToolExecutionMode.CONCURRENT_LIMITED,
            default_timeout=5.0,
            enable_circuit_breaker=False
        )
        manager = ToolExecutorManager(**config.to_dict())
        manager.set_tools({tool.name: tool for tool in mixed_tools})
        mixed_executor = AgentActionExecutor(tool_executor_manager=manager)
        
        def mixed_success_llm_chat(messages, tools):
            """LLM with mix of good and failing tool calls."""
            return ChatMessage(
                role=Role.ASSISTANT,
                content="Testing error propagation with mixed tool success/failure.",
                tool_calls=[
                    # Good tools
                    ToolCall(
                        name="timing_cpu",
                        args={"duration": 0.2, "work_type": "cpu"},
                        tool_call_id="good-1"
                    ),
                    ToolCall(
                        name="timing_io",
                        args={"duration": 0.2, "work_type": "io"},
                        tool_call_id="good-2"
                    ),
                    # Failing tool
                    ToolCall(
                        name="failing_tool",
                        args={},
                        tool_call_id="fail-1"
                    ),
                    # More good tools
                    ToolCall(
                        name="timing_mixed",
                        args={"duration": 0.2, "work_type": "mixed"},
                        tool_call_id="good-3"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=mixed_success_llm_chat,
            tools=mixed_tools,
            parser=ToolCallParser(),
            max_steps=1
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=mixed_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Test error propagation")
        ]
        
        # Execute with mixed success/failure
        observations = []
        
        for step in iterator:
            if step.type.value == "observation":
                observations.append(step.data)
            if step.type.value in ["finish", "error"] or len(observations) >= 4:
                break
        
        # Verify error isolation
        successful_obs = [obs for obs in observations if obs.success]
        failed_obs = [obs for obs in observations if not obs.success]
        
        # Should have 3 successful and 1 failed
        assert len(successful_obs) == 3, f"Wrong success count: {len(successful_obs)} != 3"
        assert len(failed_obs) == 1, f"Wrong failure count: {len(failed_obs)} != 1"
        
        # Failed observation should contain error information
        error_obs = failed_obs[0]
        assert "fail" in error_obs.action_id, f"Wrong failed tool: {error_obs.action_id}"
        assert error_obs.error is not None, "Missing error information"
        
        # Successful tools should have proper output
        for obs in successful_obs:
            assert obs.output is not None, f"Missing output for {obs.action_id}"
            assert "Completed" in obs.output, f"Unexpected output: {obs.output}"
        
        print(f"✅ Error propagation test: {len(successful_obs)} success, {len(failed_obs)} failures")


@pytest.mark.integration
@pytest.mark.concurrent
class TestConcurrentExecutionEdgeCases:
    """Edge cases and boundary conditions for concurrent execution."""

    def test_max_concurrent_equals_one_behaves_like_sequential(self, timing_test_tools):
        """Test that max_concurrent=1 behaves identically to sequential execution."""
        config = ExecutorConfig(
            max_concurrent=1,
            execution_mode=ToolExecutionMode.SEQUENTIAL,
            default_timeout=5.0,
            enable_circuit_breaker=False
        )
        manager = ToolExecutorManager(**config.to_dict())
        # Register timing test tools
        manager.set_tools({tool.name: tool for tool in timing_test_tools})
        executor = AgentActionExecutor(tool_executor_manager=manager)
        
        def sequential_test_llm_chat(messages, tools):
            return ChatMessage(
                role=Role.ASSISTANT,
                content="Testing sequential-like behavior with max_concurrent=1.",
                tool_calls=[
                    ToolCall(
                        name="timing_cpu",
                        args={"duration": 0.2, "work_type": "cpu"},
                        tool_call_id="seq-1"
                    ),
                    ToolCall(
                        name="timing_io",
                        args={"duration": 0.2, "work_type": "io"},
                        tool_call_id="seq-2"
                    ),
                    ToolCall(
                        name="timing_mixed",
                        args={"duration": 0.2, "work_type": "mixed"},
                        tool_call_id="seq-3"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=sequential_test_llm_chat,
            tools=timing_test_tools,
            parser=ToolCallParser(),
            max_steps=1
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Test sequential behavior")
        ]
        
        # Measure execution time
        start_time = time.time()
        observations = []
        
        for step in iterator:
            if step.type.value == "observation":
                observations.append(step.data)
            if step.type.value in ["finish", "error"] or len(observations) >= 3:
                break
        
        execution_time = time.time() - start_time
        
        # Should take close to sum of individual durations (3 * 0.2s = 0.6s)
        assert execution_time >= 0.5, f"Too fast for sequential: {execution_time:.3f}s < 0.5s"
        assert execution_time < 1.0, f"Too slow for sequential: {execution_time:.3f}s >= 1.0s"
        
        # All tools should complete
        assert len(observations) == 3, f"Missing observations: {len(observations)} != 3"
        
        print(f"✅ Sequential behavior test: {execution_time:.3f}s for 3 tools")

    def test_zero_duration_tools_complete_instantly(self, timing_test_tools, concurrent_action_executor):
        """Test that zero-duration tools complete without delay."""
        def instant_tools_llm_chat(messages, tools):
            return ChatMessage(
                role=Role.ASSISTANT,
                content="Testing instant completion tools.",
                tool_calls=[
                    ToolCall(
                        name="timing_cpu",
                        args={"duration": 0.0, "work_type": "cpu"},
                        tool_call_id="instant-1"
                    ),
                    ToolCall(
                        name="timing_io",
                        args={"duration": 0.0, "work_type": "io"},
                        tool_call_id="instant-2"
                    ),
                    ToolCall(
                        name="timing_mixed",
                        args={"duration": 0.0, "work_type": "mixed"},
                        tool_call_id="instant-3"
                    )
                ]
            )
        
        strategy = ReActStrategy(
            llm_chat=instant_tools_llm_chat,
            tools=timing_test_tools,
            parser=ToolCallParser(),
            max_steps=1
        )
        
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=concurrent_action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler
        )
        
        iterator.messages = [
            ChatMessage(role=Role.USER, content="Test instant tools")
        ]
        
        # Measure execution time
        start_time = time.time()
        observations = []
        
        for step in iterator:
            if step.type.value == "observation":
                observations.append(step.data)
            if step.type.value in ["finish", "error"] or len(observations) >= 3:
                break
        
        execution_time = time.time() - start_time
        
        # Should complete very quickly (< 0.1s including overhead)
        assert execution_time < 0.1, f"Too slow for instant tools: {execution_time:.3f}s >= 0.1s"
        
        # All tools should complete
        assert len(observations) == 3, f"Missing observations: {len(observations)} != 3"
        
        # All should be successful
        successful = [obs for obs in observations if obs.success]
        assert len(successful) == 3, f"Failed instant tools: {len(successful)} != 3"
        
        print(f"✅ Instant tools test: {execution_time:.3f}s for 3 zero-duration tools")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
