"""
Generic helpers for REAL FLOW testing (Phase 2A and beyond).

These helpers enable complete end-to-end flow testing with:
- Mock LLM responses with tool calls
- Flow execution and verification
- State assertions
- Reusable patterns for all priorities

✅ SOLID Design: Generic, reusable, works for ANY flow test
✅ Complete Flows: No try/except, real execution from start to finish
✅ Future-Ready: Supports Priority 1, 2, 3 tests
"""

from typing import List, Dict, Any, Optional
from unittest.mock import Mock
from mas.elements.llms.common.chat.message import ChatMessage


# ══════════════════════════════════════════════════════════════════════════════
# MOCK LLM WITH TOOL CALLS (for realistic orchestration)
# ══════════════════════════════════════════════════════════════════════════════

def create_mock_llm_with_tools(tool_call_sequences: List[List[Dict]]):
    """
    ✅ GENERIC: Create mock LLM that returns predictable tool calls.
    
    Essential for testing REAL orchestration flows where LLM makes decisions.
    Uses REAL ChatMessage and ToolCall objects for proper integration.
    
    Args:
        tool_call_sequences: List of tool call sequences, one per LLM invocation
                           Each sequence is a list of tool call dicts
                           
    Returns:
        Mock LLM that returns real ChatMessage objects with tool calls
        
    Example:
        # Orchestrator will call LLM twice: planning, then monitoring
        llm = create_mock_llm_with_tools([
            # First call: Create work plan
            [{"name": "workplan.create_or_update", "args": {...}}],
            # Second call: Check status
            [{"name": "workplan.summarize", "args": {...}}]
        ])
    """
    from mas.elements.llms.common.chat.message import ChatMessage, Role, ToolCall
    
    call_index = [0]  # Mutable to track calls
    
    def mock_chat(messages, **kwargs):
        """Return REAL ChatMessage with tool calls."""
        # Get current sequence
        if call_index[0] < len(tool_call_sequences):
            tool_call_dicts = tool_call_sequences[call_index[0]]
            call_index[0] += 1
        else:
            tool_call_dicts = []
        
        # Create REAL ToolCall objects
        tool_calls = []
        for i, tc in enumerate(tool_call_dicts):
            tool_call = ToolCall(
                name=tc.get("name", ""),
                args=tc.get("args", tc.get("arguments", {})),  # Support both 'args' and 'arguments'
                tool_call_id=f"call_{i}"
            )
            tool_calls.append(tool_call)
        
        # Return REAL ChatMessage
        return ChatMessage(
            role=Role.ASSISTANT,
            content="LLM response" if not tool_calls else "",
            tool_calls=tool_calls if tool_calls else None
        )
    
    # Create mock that supports bind_tools pattern
    mock_llm = Mock()
    mock_llm.chat = Mock(side_effect=mock_chat)
    mock_llm.name = "mock_llm"
    
    # ✅ Support bind_tools() - returns self (mock doesn't change behavior)
    mock_llm.bind_tools = Mock(return_value=mock_llm)
    
    return mock_llm


def create_planning_llm(work_items: List[Dict[str, str]]):
    """
    ✅ GENERIC: Create LLM that creates a work plan with specified items.
    
    Simulates orchestrator planning phase. Auto-generates IDs if not provided.
    
    Args:
        work_items: List of work items to create
                   Each dict can have: {"id": "...", "title": "...", "description": "...", "kind": "local/remote", ...}
                   If "id" is not provided, it will be auto-generated from title
                   
    Returns:
        Mock LLM configured for planning
        
    Example:
        llm = create_planning_llm([
            {"title": "Analyze data", "kind": "remote", "description": "Process data"},
            {"id": "custom_id", "title": "Generate report", "kind": "local", "description": "Create report"}
        ])
    """
    # ✅ Auto-generate IDs if not provided
    processed_items = []
    for i, item in enumerate(work_items):
        processed_item = item.copy()
        
        # Generate ID from title if not provided
        if "id" not in processed_item:
            # Convert title to snake_case ID
            title = processed_item.get("title", f"item_{i+1}")
            item_id = title.lower().replace(" ", "_").replace("-", "_")
            processed_item["id"] = item_id
        
        # Ensure required fields have defaults
        if "description" not in processed_item:
            processed_item["description"] = processed_item.get("title", "Work item")
        
        processed_items.append(processed_item)
    
    tool_calls = [{
        "name": "workplan.create_or_update",
        "args": {
            "summary": "Work plan created",
            "items": processed_items
        }
    }]
    
    return create_mock_llm_with_tools([tool_calls])


def create_delegating_llm(delegations: List[Dict[str, str]]):
    """
    ✅ GENERIC: Create LLM that delegates tasks to agents.
    
    Simulates orchestrator execution/delegation phase.
    
    Args:
        delegations: List of delegation instructions
                    Each dict has: {"worker_uid": "agent1", "task": "Do this"}
                    
    Returns:
        Mock LLM configured for delegation
        
    Example:
        llm = create_delegating_llm([
            {"worker_uid": "agent1", "task": "Process customer data"},
            {"worker_uid": "agent2", "task": "Generate insights"}
        ])
    """
    tool_calls = []
    for delegation in delegations:
        tool_calls.append({
            "name": "delegation.delegate_task",
            "args": delegation  # ✅ Use 'args', not 'arguments'
        })
    
    return create_mock_llm_with_tools([tool_calls])


def create_planning_and_delegating_llm(work_items: List[Dict[str, str]]):
    """
    ✅ GENERIC: Create LLM for complete orchestration flow (planning + delegation).
    
    Handles BOTH planning phase AND allocation/delegation phase.
    Essential for testing complete orchestration flows with remote work items.
    
    Args:
        work_items: List of work items (same format as create_planning_llm)
                   Remote items will automatically trigger delegation
                   
    Returns:
        Mock LLM that handles multiple orchestration phases
        
    Example:
        llm = create_planning_and_delegating_llm([
            {"title": "Process data", "kind": "remote", "assigned_uid": "agent1"},
            {"title": "Local work", "kind": "local"}
        ])
    """
    # ✅ Process items and auto-generate IDs (same as create_planning_llm)
    processed_items = []
    delegations = []
    
    for i, item in enumerate(work_items):
        processed_item = item.copy()
        
        # Generate ID from title if not provided
        if "id" not in processed_item:
            title = processed_item.get("title", f"item_{i+1}")
            item_id = title.lower().replace(" ", "_").replace("-", "_")
            processed_item["id"] = item_id
        
        # Ensure required fields
        if "description" not in processed_item:
            processed_item["description"] = processed_item.get("title", "Work item")
        
        processed_items.append(processed_item)
        
        # If remote item, prepare delegation
        if processed_item.get("kind") == "remote":
            delegation = {
                "work_item_id": processed_item["id"],  # ✅ Correct field name
                "dst_uid": processed_item.get("assigned_uid", "agent1"),  # ✅ Correct field name
                "content": processed_item["description"]  # ✅ Correct field name
            }
            delegations.append(delegation)
    
    # Build tool call sequences for BOTH phases
    sequences = []
    
    # Phase 1: Planning - create work plan
    sequences.append([{
        "name": "workplan.create_or_update",
        "args": {
            "summary": "Work plan created",
            "items": processed_items
        }
    }])
    
    # Phase 2: Allocation - delegate remote items
    if delegations:
        delegation_calls = [{
            "name": "iem.delegate_task",
            "args": delegation
        } for delegation in delegations]
        sequences.append(delegation_calls)
    
    return create_mock_llm_with_tools(sequences)


# ══════════════════════════════════════════════════════════════════════════════
# FLOW EXECUTION HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def execute_orchestrator_cycle(orchestrator, state_view, initial_task=None):
    """
    ✅ GENERIC: Execute ONE complete orchestration cycle.
    
    Runs: packet processing → planning → execution → monitoring
    
    Args:
        orchestrator: OrchestratorNode instance
        state_view: StateView with proper permissions
        initial_task: Optional initial task to add to inbox
                     NOTE: If task has thread_id, the thread must already exist!
                           If no thread_id, orchestrator will create one automatically.
        
    Returns:
        Tuple of (updated_state_view, thread_id_used)
        
    Example:
        task = Task(content="Build report")  # No thread_id - orchestrator creates it
        result_state, thread_id = execute_orchestrator_cycle(orch, state_view, initial_task=task)
    """
    from tests.base import add_packet_to_inbox, create_task_packet
    from mas.graph.state.graph_state import Channel
    
    # Add initial task if provided
    if initial_task:
        packet = create_task_packet("user1", orchestrator._ctx.uid, initial_task)
        add_packet_to_inbox(state_view, orchestrator._ctx.uid, packet)
    
    # Execute orchestrator
    result_state = orchestrator.run(state_view)
    
    # ✅ Get the thread_id using ThreadService (proper API!)
    thread_id = None
    if initial_task and initial_task.thread_id:
        thread_id = initial_task.thread_id
    else:
        # Use orchestrator's thread service to find root threads
        # This is the CORRECT way - uses the same API as production code
        thread_service = orchestrator.threads  # From WorkloadCapableMixin
        root_threads = thread_service.list_root_threads()
        
        if root_threads:
            # For single-task scenarios, get the first (and usually only) root thread
            thread_id = root_threads[0].thread_id
    
    return result_state, thread_id


def execute_agent_work(agent, state_view, task):
    """
    ✅ GENERIC: Execute agent processing a task.
    
    Simulates agent receiving task and processing it.
    
    Args:
        agent: CustomAgentNode instance
        state_view: StateView with proper permissions
        task: Task for agent to process
        
    Returns:
        Updated state_view after processing
        
    Example:
        task = Task(content="Analyze this", thread_id="t1")
        result_state = execute_agent_work(agent, state_view, task)
    """
    from tests.base import add_packet_to_inbox, create_task_packet
    
    # Deliver task to agent
    packet = create_task_packet(task.created_by, agent._ctx.uid, task)
    add_packet_to_inbox(state_view, agent._ctx.uid, packet)
    
    # Execute agent
    result_state = agent.run(state_view)
    return result_state


# ══════════════════════════════════════════════════════════════════════════════
# FLOW VERIFICATION HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def assert_llm_called_with_tools(mock_llm, expected_tool_names: List[str]):
    """
    ✅ GENERIC: Assert LLM was called and specific tools were available.
    
    Args:
        mock_llm: Mock LLM instance
        expected_tool_names: List of tool names that should have been available
        
    Example:
        assert_llm_called_with_tools(mock_llm, ["workplan.create_or_update", "delegation.delegate_task"])
    """
    assert mock_llm.chat.called, "LLM was not called"
    
    # Get the tools argument from the call
    call_args = mock_llm.chat.call_args
    if call_args:
        _, kwargs = call_args
        tools = kwargs.get('tools', [])
        
        if tools:
            tool_names = [t.name if hasattr(t, 'name') else str(t) for t in tools]
            for expected in expected_tool_names:
                assert any(expected in tn for tn in tool_names), \
                    f"Tool {expected} not found in {tool_names}"


def assert_packets_sent(state, from_uid: str, to_uid: str, min_count: int = 1):
    """
    ✅ GENERIC: Assert packets were sent from one node to another.
    
    Args:
        state: GraphState or StateView
        from_uid: Source node UID
        to_uid: Destination node UID
        min_count: Minimum number of packets expected
        
    Example:
        assert_packets_sent(state_view, "orch1", "agent1", min_count=1)
    """
    from tests.base import get_packets_from_outbox
    
    packets = get_packets_from_outbox(state, from_uid)
    matching = [p for p in packets if hasattr(p, 'dst') and p.dst.uid == to_uid]
    
    assert len(matching) >= min_count, \
        f"Expected at least {min_count} packets from {from_uid} to {to_uid}, found {len(matching)}"
    
    return matching


def assert_work_plan_created(orchestrator, thread_id: str):
    """
    ✅ GENERIC: Assert work plan was created for thread.
    
    Args:
        orchestrator: OrchestratorNode instance
        thread_id: Thread ID to check
        
    Returns:
        The work plan if found
        
    Example:
        plan = assert_work_plan_created(orch, "thread1")
        assert len(plan.items) > 0
    """
    service = orchestrator.get_workload_service()
    workspace_service = service.get_workspace_service()
    
    plan = workspace_service.load_work_plan(thread_id, orchestrator._ctx.uid)
    assert plan is not None, f"Work plan not found for thread {thread_id}"
    
    return plan


def assert_work_plan_has_items(plan, expected_count: int = None, expected_kinds: List[str] = None):
    """
    ✅ GENERIC: Assert work plan has expected items.
    
    Args:
        plan: WorkPlan instance
        expected_count: Expected number of items (None = don't check)
        expected_kinds: Expected item kinds (None = don't check)
        
    Example:
        assert_work_plan_has_items(plan, expected_count=3, expected_kinds=["remote", "remote", "local"])
    """
    if expected_count is not None:
        assert len(plan.items) == expected_count, \
            f"Expected {expected_count} items, found {len(plan.items)}"
    
    if expected_kinds is not None:
        actual_kinds = [item.kind.value for item in plan.items.values()]
        assert actual_kinds == expected_kinds, \
            f"Expected kinds {expected_kinds}, found {actual_kinds}"


def get_delegation_packets(state, from_uid: str):
    """
    ✅ GENERIC: Get all delegation packets sent by orchestrator.
    
    Args:
        state: GraphState or StateView
        from_uid: Orchestrator UID
        
    Returns:
        List of task packets (delegation packets)
        
    Example:
        delegations = get_delegation_packets(state_view, "orch1")
        assert len(delegations) == 2
    """
    from tests.base import get_packets_from_outbox
    from mas.core.iem.models import PacketType
    
    packets = get_packets_from_outbox(state, from_uid)
    # Filter for task packets (delegations)
    return [p for p in packets if hasattr(p, 'type') and p.type == PacketType.TASK]


# ══════════════════════════════════════════════════════════════════════════════
# COMPLETE FLOW PATTERNS (for common test scenarios)
# ══════════════════════════════════════════════════════════════════════════════

def run_orchestration_flow(orchestrator, agent, initial_task, mock_llm):
    """
    ✅ GENERIC: Run complete orchestration flow: orch plans → delegates → agent works.
    
    Complete flow pattern reusable across ALL tests.
    
    Args:
        orchestrator: OrchestratorNode
        agent: CustomAgentNode  
        initial_task: Initial task for orchestrator
        mock_llm: Mock LLM (should return appropriate tool calls)
        
    Returns:
        Dict with flow results: {
            "orch_state": StateView,
            "agent_state": StateView,
            "work_plan": WorkPlan,
            "delegations": List[packets],
            "thread_id": str (root thread ID created by orchestrator)
        }
        
    Example:
        results = run_orchestration_flow(orch, agent, task, planning_llm)
        assert results["work_plan"] is not None
        assert len(results["delegations"]) > 0
    """
    from tests.base import setup_node_for_execution
    
    # Setup orchestrator
    orch_state, _ = setup_node_for_execution(orchestrator, orchestrator._ctx.uid, [agent._ctx.uid])
    
    # ✅ Execute orchestrator cycle (returns state AND thread_id)
    orch_state, thread_id = execute_orchestrator_cycle(orchestrator, orch_state, initial_task)
    
    # ✅ Get work plan using dynamic thread_id
    work_plan = assert_work_plan_created(orchestrator, thread_id)
    
    # Get delegations
    delegations = get_delegation_packets(orch_state, orchestrator._ctx.uid)
    
    # Setup agent (if delegations exist)
    agent_state = None
    if delegations:
        agent_state, _ = setup_node_for_execution(agent, agent._ctx.uid, [])
        
        # Deliver first delegation to agent
        from tests.base import add_packet_to_inbox
        add_packet_to_inbox(agent_state, agent._ctx.uid, delegations[0])
        
        # Execute agent
        agent_state = agent.run(agent_state)
    
    return {
        "orch_state": orch_state,
        "agent_state": agent_state,
        "work_plan": work_plan,
        "delegations": delegations,
        "thread_id": thread_id  # ✅ Include dynamic thread_id for downstream use
    }


# ══════════════════════════════════════════════════════════════════════════════
# MULTI-ROUND ORCHESTRATION HELPERS (Phase 2A Priority 2)
# ══════════════════════════════════════════════════════════════════════════════

def create_stateful_llm(responses_per_call: List[List[Dict]]):
    """
    ✅ GENERIC: Create LLM that changes behavior based on call count.
    
    Essential for multi-round orchestration where LLM behaves differently
    in each cycle (e.g., planning → monitoring → synthesis).
    
    Args:
        responses_per_call: List of tool call sequences, one for EACH LLM invocation
                           LLM returns responses_per_call[i] on the (i+1)th call
                           
    Returns:
        Mock LLM that tracks call count and returns different responses
        
    Example:
        # LLM will be called 3 times across multiple orchestration cycles
        llm = create_stateful_llm([
            [{"name": "workplan.create_or_update", "args": {...}}],  # Call 1: Planning
            [{"name": "iem.delegate_task", "args": {...}}],          # Call 2: Delegation
            [{"name": "workplan.mark", "args": {...}}]               # Call 3: Monitoring
        ])
    """
    return create_mock_llm_with_tools(responses_per_call)


def create_simple_agent_llm(response_content: str):
    """
    ✅ GENERIC: Create a simple mock LLM for agents that just return content (no tools).
    
    For agents without tools, the LLM just needs to return final answer content.
    This is cleaner than using create_stateful_llm which is designed for tool calls.
    
    Useful for: CustomAgentNode tests where agent completes work without using tools.
    Works for: ANY agent that returns simple text responses.
    
    Args:
        response_content: The content the agent should return
        
    Returns:
        Mock LLM configured to return the content with no tool calls
        
    Example:
        # Create agent that returns simple response
        agent_llm = create_simple_agent_llm("Analysis complete: Found 150 records")
        agent = create_custom_agent_node("agent1", agent_llm)
        
        # Use in real flow test
        state = execute_agent_work(agent, state, task)
    """
    from mas.elements.llms.common.chat.message import ChatMessage, Role
    
    llm = Mock()
    llm.chat = Mock(return_value=ChatMessage(
        role=Role.ASSISTANT,
        content=response_content,
        tool_calls=[]  # No tools = final answer
    ))
    return llm


def create_stateful_agent_llm(responses: List[str]):
    """
    ✅ GENERIC: Create a stateful mock LLM for agents with different text per call.
    
    For multi-round agent scenarios where the agent returns different text
    for each invocation (e.g., clarification requests, then final answer).
    
    Useful for: Testing multi-round agent behavior without tools.
    Works for: ANY agent that needs different responses per call.
    
    Args:
        responses: List of text responses, one per LLM call
        
    Returns:
        Mock LLM that returns different text content on each call
        
    Example:
        # Agent asks for clarification twice, then completes
        agent_llm = create_stateful_agent_llm([
            "CLARIFICATION: Which time period?",      # Call 1
            "CLARIFICATION: Include social media?",   # Call 2
            "Analysis complete: 65% positive"         # Call 3
        ])
        agent = create_custom_agent_node("agent1", agent_llm)
        
        # Each execute_agent_work call gets the next response
        state = execute_agent_work(agent, state, task1)  # Returns response[0]
        state = execute_agent_work(agent, state, task2)  # Returns response[1]
        state = execute_agent_work(agent, state, task3)  # Returns response[2]
    """
    from mas.elements.llms.common.chat.message import ChatMessage, Role
    
    llm = Mock()
    call_count = [0]  # Mutable counter
    
    def chat_handler(messages, **kwargs):
        if call_count[0] < len(responses):
            content = responses[call_count[0]]
            call_count[0] += 1
        else:
            # Fallback if called more times than responses provided
            content = f"Extra call {call_count[0] - len(responses) + 1}"
            call_count[0] += 1
        
        return ChatMessage(
            role=Role.ASSISTANT,
            content=content,
            tool_calls=[]  # No tools = final answer
        )
    
    llm.chat = Mock(side_effect=chat_handler)
    
    return llm


def create_multi_round_planning_llm(rounds: List[Dict]):
    """
    ✅ GENERIC: Create LLM for multi-round orchestration with different actions per round.
    
    Each round can have: planning, delegation, monitoring, or synthesis actions.
    
    Args:
        rounds: List of round configurations, each containing:
               {
                   "action": "plan" | "delegate" | "mark" | "summarize" | "finish",
                   "items": [...] (for plan),
                   "delegations": [...] (for delegate),
                   "marks": [...] (for mark),
                   ...
               }
               
    Returns:
        Stateful mock LLM for multi-round orchestration
        
    Example:
        llm = create_multi_round_planning_llm([
            {"action": "plan", "items": [{"title": "Task 1", "kind": "remote", "assigned_uid": "agent1"}]},
            {"action": "delegate", "work_item_id": "task_1", "dst_uid": "agent1"},
            {"action": "mark", "work_item_id": "task_1", "status": "done"},
            {"action": "finish"}
        ])
    """
    from mas.elements.llms.common.chat.message import ChatMessage, Role
    
    sequences = []
    
    for round_config in rounds:
        action = round_config.get("action")
        
        if action == "plan":
            items = round_config.get("items", [])
            # Process items like create_planning_llm
            processed_items = []
            for i, item in enumerate(items):
                processed_item = item.copy()
                if "id" not in processed_item:
                    title = processed_item.get("title", f"item_{i+1}")
                    item_id = title.lower().replace(" ", "_").replace("-", "_")
                    processed_item["id"] = item_id
                if "description" not in processed_item:
                    processed_item["description"] = processed_item.get("title", "Work item")
                processed_items.append(processed_item)
            
            sequences.append([{
                "name": "workplan.create_or_update",
                "args": {
                    "summary": round_config.get("summary", "Work plan updated"),
                    "items": processed_items
                }
            }])
            
        elif action == "delegate":
            sequences.append([{
                "name": "iem.delegate_task",
                "args": {
                    "work_item_id": round_config.get("work_item_id"),
                    "dst_uid": round_config.get("dst_uid"),
                    "content": round_config.get("content", "Delegated task")
                }
            }])
            
        elif action == "mark":
            sequences.append([{
                "name": "workplan.mark",
                "args": {
                    "item_id": round_config.get("item_id", round_config.get("work_item_id")),  # Support both for backwards compat
                    "status": round_config.get("status", "done"),
                    "notes": round_config.get("notes", round_config.get("reason", "Work completed"))  # Support both
                }
            }])
            
        elif action == "summarize":
            sequences.append([{
                "name": "workplan.summarize",
                "args": {}
            }])
            
        elif action == "finish":
            # No tool calls - LLM just finishes
            sequences.append([])
    
    return create_stateful_llm(sequences)


def run_orchestration_until_complete(orchestrator, state_view, initial_task=None, max_cycles=10):
    """
    ✅ GENERIC: Run orchestrator for MULTIPLE cycles until work is complete.
    
    Critical for testing multi-round orchestration patterns.
    
    Args:
        orchestrator: OrchestratorNode instance
        state_view: StateView with proper permissions
        initial_task: Optional initial task (for first cycle only)
        max_cycles: Maximum cycles to prevent infinite loops (default 10)
        
    Returns:
        Dict with:
            "final_state": Final StateView,
            "thread_id": Thread ID used,
            "cycle_count": Number of cycles executed,
            "work_plan": Final work plan
            
    Example:
        result = run_orchestration_until_complete(orch, state_view, task, max_cycles=5)
        assert result["cycle_count"] == 3
        assert result["work_plan"].is_complete()
    """
    cycle_count = 0
    current_state = state_view
    thread_id = None
    
    # First cycle with initial task
    if initial_task:
        current_state, thread_id = execute_orchestrator_cycle(orchestrator, current_state, initial_task)
        cycle_count += 1
    
    # Continue cycles until complete or max reached
    while cycle_count < max_cycles:
        # Check if work plan is complete
        service = orchestrator.get_workload_service()
        workspace_service = service.get_workspace_service()
        
        # Get thread_id if not set (from first cycle)
        if thread_id is None:
            root_threads = orchestrator.threads.list_root_threads()
            if root_threads:
                thread_id = root_threads[0].thread_id
            else:
                break  # No threads, nothing to do
        
        plan = workspace_service.load_work_plan(thread_id, orchestrator._ctx.uid)
        
        if plan and plan.is_complete():
            break
        
        # Run another cycle
        current_state, _ = execute_orchestrator_cycle(orchestrator, current_state)
        cycle_count += 1
    
    # Get final work plan
    final_plan = None
    if thread_id:
        service = orchestrator.get_workload_service()
        workspace_service = service.get_workspace_service()
        final_plan = workspace_service.load_work_plan(thread_id, orchestrator._ctx.uid)
    
    return {
        "final_state": current_state,
        "thread_id": thread_id,
        "cycle_count": cycle_count,
        "work_plan": final_plan
    }


def create_monitoring_llm(item_id: str, status: str = "done", notes: str = "Work completed"):
    """
    ✅ GENERIC: Create LLM for monitoring phase that marks work items.
    
    Simulates LLM interpreting responses and marking work item status.
    
    Args:
        item_id: Work item ID to mark
        status: Status to set ("done", "failed", etc.)
        notes: Notes explaining status change
        
    Returns:
        Mock LLM configured for monitoring phase
        
    Example:
        llm = create_monitoring_llm("task_1", status="done", notes="Agent completed successfully")
    """
    return create_mock_llm_with_tools([[{
        "name": "workplan.mark",
        "args": {
            "item_id": item_id,
            "status": status,
            "notes": notes
        }
    }]])


def assert_orchestration_cycle_count(actual_count: int, expected_count: int, tolerance: int = 0):
    """
    ✅ GENERIC: Assert orchestration ran expected number of cycles.
    
    Args:
        actual_count: Actual number of cycles executed
        expected_count: Expected number of cycles
        tolerance: Acceptable variance (e.g., ±1 cycle)
        
    Example:
        assert_orchestration_cycle_count(result["cycle_count"], 3, tolerance=1)
    """
    min_expected = expected_count - tolerance
    max_expected = expected_count + tolerance
    
    assert min_expected <= actual_count <= max_expected, \
        f"Expected {expected_count} cycles (±{tolerance}), but got {actual_count}"


def assert_work_plan_complete(plan):
    """
    ✅ GENERIC: Assert work plan is complete.
    
    Args:
        plan: WorkPlan instance
        
    Example:
        assert_work_plan_complete(final_plan)
    """
    assert plan is not None, "Work plan is None"
    assert plan.is_complete(), \
        f"Work plan not complete. Status: {plan.get_status_counts()}"


def get_work_plan_status_counts(plan):
    """
    ✅ GENERIC: Get work plan status counts for assertions.
    
    Args:
        plan: WorkPlan instance
        
    Returns:
        Dict with status counts (waiting calculated as IN_PROGRESS + REMOTE items)
        
    Example:
        counts = get_work_plan_status_counts(plan)
        assert counts["done"] == 3
    """
    if not plan:
        return {}
    
    from mas.elements.nodes.common.workload import WorkItemStatus, WorkItemKind
    
    status_counts = plan.get_status_counts()
    
    # Calculate waiting items (IN_PROGRESS + REMOTE)
    waiting_count = sum(
        1 for item in plan.items.values()
        if item.status == WorkItemStatus.IN_PROGRESS and item.kind == WorkItemKind.REMOTE
    )
    
    return {
        "pending": status_counts.pending,
        "waiting": waiting_count,  # Calculated from IN_PROGRESS + REMOTE
        "in_progress": status_counts.in_progress,
        "done": status_counts.done,
        "failed": status_counts.failed,
        "blocked": status_counts.blocked,
        "total": status_counts.total
    }


# ══════════════════════════════════════════════════════════════════════════════
# DELEGATION & RESPONSE SIMULATION (Generic Round-Trip Helpers)
# ══════════════════════════════════════════════════════════════════════════════

def simulate_delegation_responses(
    state_view,
    orch_uid: str,
    response_content: str = "Task completed successfully",
    success: bool = True,
    response_per_delegation: Optional[Dict[int, Dict[str, Any]]] = None
):
    """
    ✅ GENERIC: Simulate responses for ALL pending delegations from an orchestrator.
    
    This eliminates the repetitive pattern of:
    1. Get delegations
    2. Loop through delegations
    3. Create response for each
    4. Add to inbox
    
    Args:
        state_view: StateView instance
        orch_uid: Orchestrator UID
        response_content: Default response content (if response_per_delegation not provided)
        success: Default success status
        response_per_delegation: Optional dict mapping delegation index to custom response
                                 Format: {0: {"content": "...", "success": True, "result": {...}}}
    
    Returns:
        List of simulated responses
        
    Example:
        # Simple: respond to all delegations with same content
        responses = simulate_delegation_responses(state_view, "orch1", "All done!")
        
        # Advanced: custom response per delegation
        responses = simulate_delegation_responses(
            state_view, "orch1",
            response_per_delegation={
                0: {"content": "Task 1 done", "success": True},
                1: {"content": "Task 2 failed", "success": False}
            }
        )
    """
    from tests.base import (
        get_delegation_packets, create_response_task,
        create_task_packet, add_packet_to_inbox
    )
    
    # Get all delegations
    delegations = get_delegation_packets(state_view, orch_uid)
    
    if not delegations:
        return []
    
    responses = []
    
    for i, delegation_packet in enumerate(delegations):
        delegated_task = delegation_packet.extract_task()
        from_uid = delegation_packet.dst.uid  # Agent that should respond
        
        # Determine response content/success
        if response_per_delegation and i in response_per_delegation:
            custom = response_per_delegation[i]
            content = custom.get("content", response_content)
            is_success = custom.get("success", success)
            result_data = custom.get("result", None)
        else:
            content = response_content
            is_success = success
            result_data = None
        
        # Create response
        response = create_response_task(
            delegated_task,
            content,
            from_uid=from_uid,
            success=is_success
        )
        
        # Add result data if provided
        if result_data:
            response.result = result_data
        
        # Send response back to orchestrator
        response_packet = create_task_packet(from_uid, orch_uid, response)
        add_packet_to_inbox(state_view, orch_uid, response_packet)
        
        responses.append(response)
    
    return responses


def execute_cycle_and_respond(
    orchestrator,
    state_view,
    initial_task=None,
    response_content: str = "Task completed successfully",
    success: bool = True,
    custom_responses: Optional[Dict[int, Dict[str, Any]]] = None
):
    """
    ✅ GENERIC: Execute orchestration cycle AND auto-simulate responses.
    
    This is the MOST COMMON pattern in multi-round tests:
    1. Run orchestrator cycle
    2. Get delegations
    3. Simulate responses
    4. Return state for next cycle
    
    Args:
        orchestrator: Orchestrator node
        state_view: StateView instance
        initial_task: Optional initial task (for first cycle)
        response_content: Default response content
        success: Default success status
        custom_responses: Optional custom responses per delegation
        
    Returns:
        Tuple of (updated_state_view, thread_id, delegations, responses)
        
    Example:
        # Simple: execute cycle + auto-respond
        state, thread_id, delegations, responses = execute_cycle_and_respond(
            orch, state_view, initial_task
        )
        
        # Advanced: custom responses
        state, thread_id, delegations, responses = execute_cycle_and_respond(
            orch, state_view,
            custom_responses={
                0: {"content": "Done!", "success": True},
                1: {"content": "Failed", "success": False}
            }
        )
    """
    from tests.base import get_delegation_packets
    
    # Execute orchestration cycle
    result_state, thread_id = execute_orchestrator_cycle(
        orchestrator, state_view, initial_task
    )
    
    # Get delegations from this cycle
    delegations = get_delegation_packets(result_state, orchestrator.uid)
    
    # Simulate responses for all delegations
    responses = simulate_delegation_responses(
        result_state,
        orchestrator.uid,
        response_content=response_content,
        success=success,
        response_per_delegation=custom_responses
    )
    
    return result_state, thread_id, delegations, responses


def get_latest_delegations(state_view, orch_uid: str, count: int = None):
    """
    ✅ GENERIC: Get the latest N delegations from an orchestrator.
    
    Useful when you need to respond to only the NEWEST delegations
    (e.g., after a retry or dynamic plan expansion).
    
    Args:
        state_view: StateView instance
        orch_uid: Orchestrator UID
        count: Number of latest delegations to get (None = all)
        
    Returns:
        List of latest delegation packets
        
    Example:
        # Get only the last delegation (e.g., after retry)
        latest = get_latest_delegations(state_view, "orch1", count=1)
        
        # Get last 2 delegations (e.g., after adding 2 new items)
        latest = get_latest_delegations(state_view, "orch1", count=2)
    """
    from tests.base import get_delegation_packets
    
    all_delegations = get_delegation_packets(state_view, orch_uid)
    
    if not all_delegations:
        return []
    
    if count is None:
        return all_delegations
    
    # Return last N delegations
    return all_delegations[-count:] if count > 0 else []


def simulate_specific_responses(
    state_view,
    orch_uid: str,
    delegation_indices: List[int],
    responses: List[Dict[str, Any]]
):
    """
    ✅ GENERIC: Simulate responses for SPECIFIC delegations by index.
    
    Useful for testing gradual response arrival or selective failures.
    
    Args:
        state_view: StateView instance
        orch_uid: Orchestrator UID
        delegation_indices: Indices of delegations to respond to
        responses: List of response dicts (one per index)
                  Format: [{"content": "...", "success": True, "result": {...}}]
    
    Returns:
        List of simulated responses
        
    Example:
        # Respond to only delegations 0 and 2
        simulate_specific_responses(
            state_view, "orch1",
            delegation_indices=[0, 2],
            responses=[
                {"content": "Task 0 done", "success": True},
                {"content": "Task 2 done", "success": True}
            ]
        )
    """
    from tests.base import (
        get_delegation_packets, create_response_task,
        create_task_packet, add_packet_to_inbox
    )
    
    all_delegations = get_delegation_packets(state_view, orch_uid)
    
    if not all_delegations:
        return []
    
    simulated_responses = []
    
    for idx, response_config in zip(delegation_indices, responses):
        if idx >= len(all_delegations):
            continue
        
        delegation_packet = all_delegations[idx]
        delegated_task = delegation_packet.extract_task()
        from_uid = delegation_packet.dst.uid
        
        # Create response
        response = create_response_task(
            delegated_task,
            response_config.get("content", "Done"),
            from_uid=from_uid,
            success=response_config.get("success", True)
        )
        
        # Add result data if provided
        if "result" in response_config:
            response.result = response_config["result"]
        
        # Send response
        response_packet = create_task_packet(from_uid, orch_uid, response)
        add_packet_to_inbox(state_view, orch_uid, response_packet)
        
        simulated_responses.append(response)
    
    return simulated_responses
