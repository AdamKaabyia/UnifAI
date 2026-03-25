"""
Base test class for all node tests.

Provides common setup/teardown and helper methods that all node tests can use.
Follows SOLID principles with clear separation of concerns.
"""

import pytest
from typing import List, Dict, Any, Optional, Type
from unittest.mock import Mock

from mas.graph.state.state_view import StateView
from mas.graph.state.graph_state import GraphState
from mas.graph.models import StepContext
from mas.elements.nodes.common.workload import Task, WorkPlan, UnifiedWorkloadService
from mas.core.iem.packets import TaskPacket
from mas.core.iem.models import ElementAddress


class BaseNodeTest:
    """
    Base class for all node tests.
    
    Provides common setup/teardown and helper methods that reduce duplication
    and ensure consistent test infrastructure across all node types.
    
    Usage:
        class TestMyNode(BaseNodeTest):
            def test_something(self):
                node = self.create_node_with_state(MyNode, "test_node")
                # ... test logic
    """
    
    # Automatically injected by pytest fixtures
    state: StateView = None
    graph_state: GraphState = None
    
    @pytest.fixture(autouse=True)
    def setup_node_test(self, graph_state, state_view):
        """Auto-used fixture to setup common node test infrastructure."""
        self.graph_state = graph_state
        self.state = state_view
        yield
        # Cleanup after test
        self.state = None
        self.graph_state = None
    
    def create_node_with_state(
        self, 
        node_class: Type,
        uid: str,
        adjacent_nodes: List[str] = None,
        **node_kwargs
    ):
        """
        Factory method to create and configure a node with state and context.
        
        Args:
            node_class: The node class to instantiate
            uid: Unique identifier for the node
            adjacent_nodes: List of adjacent node UIDs
            **node_kwargs: Additional arguments to pass to node constructor
            
        Returns:
            Configured node instance with state and context set up
        """
        from tests.base.test_helpers import create_test_step_context
        
        # Create the node instance
        node = node_class(**node_kwargs)
        
        # Set up context with adjacency
        step_context = create_test_step_context(uid, adjacent_nodes or [])
        node.set_context(step_context)
        
        # Set up state
        node._state = self.state
        
        return node
    
    def send_task_to_node(
        self, 
        node, 
        task: Task,
        src_uid: str = "test_sender"
    ) -> TaskPacket:
        """
        Helper to send task packet to node.
        
        Args:
            node: The node to send the task to
            task: The task to send
            src_uid: Source UID for the packet
            
        Returns:
            The created TaskPacket
        """
        packet = TaskPacket.create(
            src=ElementAddress(uid=src_uid),
            dst=ElementAddress(uid=node.uid),
            task=task
        )
        
        # Add to state for processing
        self.state.inter_packets.append(packet)
        
        # Process the packet
        node.handle_task_packet(packet)
        
        return packet
    
    def get_workspace(self, thread_id: str):
        """Get workspace for a thread from the node's workload service."""
        from mas.elements.nodes.common.workload import UnifiedWorkloadService, StateBoundStorage
        storage = StateBoundStorage(self.state)
        service = UnifiedWorkloadService(storage)
        return service.get_workspace(thread_id)
    
    def get_thread(self, thread_id: str):
        """Get thread from the workload service."""
        from mas.elements.nodes.common.workload import UnifiedWorkloadService, StateBoundStorage
        storage = StateBoundStorage(self.state)
        service = UnifiedWorkloadService(storage)
        return service.get_thread(thread_id)
    
    def assert_workspace_updated(
        self, 
        thread_id: str,
        expected_facts: Optional[List[str]] = None,
        expected_variables: Optional[Dict[str, Any]] = None
    ):
        """
        Assert workspace was updated correctly.
        
        Args:
            thread_id: Thread ID to check
            expected_facts: List of facts that should be in workspace context
            expected_variables: Dict of variables that should be in workspace
        """
        workspace = self.get_workspace(thread_id)
        assert workspace is not None, f"Workspace not found for thread {thread_id}"
        
        if expected_facts:
            actual_facts = workspace.context.facts
            for fact in expected_facts:
                assert any(fact in f for f in actual_facts), \
                    f"Expected fact '{fact}' not found in workspace. Actual: {actual_facts}"
        
        if expected_variables:
            for key, expected_value in expected_variables.items():
                actual_value = workspace.variables.get(key)
                assert actual_value == expected_value, \
                    f"Variable '{key}' mismatch. Expected: {expected_value}, Actual: {actual_value}"
    
    def assert_workplan_exists(
        self,
        thread_id: str,
        owner_uid: str,
        min_items: int = 1
    ) -> WorkPlan:
        """
        Assert workplan exists and has minimum number of items.
        
        Args:
            thread_id: Thread ID to check
            owner_uid: Owner UID of the workplan
            min_items: Minimum number of items expected
            
        Returns:
            The WorkPlan if found
        """
        from mas.elements.nodes.common.workload import UnifiedWorkloadService, StateBoundStorage
        storage = StateBoundStorage(self.state)
        service = UnifiedWorkloadService(storage)
        
        # Use current API: workspaces.load_work_plan() instead of deprecated WorkPlanService
        work_plan = service.get_workspace_service().load_work_plan(thread_id, owner_uid)
        assert work_plan is not None, f"WorkPlan not found for thread={thread_id}, owner={owner_uid}"
        assert len(work_plan.items) >= min_items, \
            f"WorkPlan has {len(work_plan.items)} items, expected at least {min_items}"
        
        return work_plan
    
    def create_mock_adjacent_nodes(self, count: int = 2) -> Dict[str, Dict[str, Any]]:
        """
        Create mock adjacent nodes for testing.
        
        Args:
            count: Number of adjacent nodes to create
            
        Returns:
            Dict mapping node UIDs to their metadata
        """
        return {
            f"node_{i}": {
                "type": f"test_node_{i}",
                "specialization": f"Test specialization {i}"
            }
            for i in range(1, count + 1)
        }


class BaseOrchestratorTest(BaseNodeTest):
    """
    Base class for orchestrator tests with orchestrator-specific helpers.
    
    Extends BaseNodeTest with orchestrator-specific utilities like workplan
    management, delegation testing, and worker node simulation.
    """
    
    def create_orchestrator_with_workers(
        self,
        uid: str = "test_orchestrator",
        worker_count: int = 2,
        llm = None,
        **kwargs
    ):
        """
        Create orchestrator with configured worker nodes.
        
        Args:
            uid: Orchestrator UID
            worker_count: Number of worker nodes to create
            llm: LLM instance (defaults to mock if not provided)
            **kwargs: Additional arguments for OrchestratorNode
            
        Returns:
            Configured OrchestratorNode instance
        """
        from mas.elements.nodes.orchestrator.orchestrator_node import OrchestratorNode
        from tests.fixtures.common.llm_fixtures import create_mock_llm
        
        if llm is None:
            llm = create_mock_llm()
        
        # Create worker node UIDs
        worker_uids = [f"worker_{i}" for i in range(1, worker_count + 1)]
        
        # Create orchestrator with workers
        orchestrator = self.create_node_with_state(
            OrchestratorNode,
            uid=uid,
            adjacent_nodes=worker_uids,
            llm=llm,
            **kwargs
        )
        
        return orchestrator
    
    def assert_workplan_created(
        self,
        thread_id: str,
        orchestrator_uid: str,
        min_items: int = 1,
        expected_item_ids: Optional[List[str]] = None
    ) -> WorkPlan:
        """
        Assert workplan was created with expected items.
        
        Args:
            thread_id: Thread ID to check
            orchestrator_uid: Orchestrator UID that owns the workplan
            min_items: Minimum number of items expected
            expected_item_ids: Specific item IDs that should exist
            
        Returns:
            The WorkPlan
        """
        work_plan = self.assert_workplan_exists(thread_id, orchestrator_uid, min_items)
        
        if expected_item_ids:
            actual_item_ids = set(work_plan.items.keys())
            expected_set = set(expected_item_ids)
            assert expected_set.issubset(actual_item_ids), \
                f"Expected items {expected_set} not found. Actual: {actual_item_ids}"
        
        return work_plan
    
    def assert_task_delegated(
        self,
        dst_uid: str,
        task_content: str = None
    ):
        """
        Assert task was delegated to specified node.
        
        Args:
            dst_uid: Destination node UID
            task_content: Optional content to verify in task
        """
        # Check inter_packets for delegation
        packets = self.state.inter_packets
        
        delegated_packets = [
            p for p in packets 
            if hasattr(p, 'dst') and p.dst.uid == dst_uid
        ]
        
        assert len(delegated_packets) > 0, \
            f"No tasks delegated to {dst_uid}. Found packets to: {[p.dst.uid for p in packets if hasattr(p, 'dst')]}"
        
        if task_content:
            found = any(
                task_content in p.extract_task().content 
                for p in delegated_packets
            )
            assert found, f"Task content '{task_content}' not found in delegated tasks"


class BaseCustomAgentTest(BaseNodeTest):
    """
    Base class for custom agent tests with agent-specific helpers.
    
    Extends BaseNodeTest with custom agent-specific utilities like tool
    management, response routing verification, and agent result checking.
    """
    
    def create_agent_with_tools(
        self,
        uid: str = "test_agent",
        tools: List = None,
        llm = None,
        strategy_type: str = "react",
        **kwargs
    ):
        """
        Create custom agent with tools configured.
        
        Args:
            uid: Agent UID
            tools: List of tools to configure
            llm: LLM instance (defaults to mock if not provided)
            strategy_type: Strategy type (react, plan_execute, etc.)
            **kwargs: Additional arguments for CustomAgentNode
            
        Returns:
            Configured CustomAgentNode instance
        """
        from mas.elements.nodes.custom_agent.custom_agent import CustomAgentNode
        from tests.fixtures.common.llm_fixtures import create_mock_llm
        
        if llm is None:
            llm = create_mock_llm()
        
        if tools is None:
            from tests.fixtures.common.tool_fixtures import create_basic_test_tools
            tools = create_basic_test_tools()
        
        agent = self.create_node_with_state(
            CustomAgentNode,
            uid=uid,
            llm=llm,
            tools=tools,
            strategy_type=strategy_type,
            **kwargs
        )
        
        return agent
    
    def assert_response_routed_to(
        self,
        dst_uid: str,
        from_agent_uid: str = None
    ):
        """
        Assert response was routed to expected destination.
        
        Args:
            dst_uid: Expected destination UID
            from_agent_uid: Optional source agent UID to filter by
        """
        packets = self.state.inter_packets
        
        response_packets = [
            p for p in packets
            if hasattr(p, 'dst') and p.dst.uid == dst_uid
        ]
        
        if from_agent_uid:
            response_packets = [
                p for p in response_packets
                if hasattr(p, 'src') and p.src.uid == from_agent_uid
            ]
        
        assert len(response_packets) > 0, \
            f"No responses routed to {dst_uid}" + \
            (f" from {from_agent_uid}" if from_agent_uid else "")
    
    def assert_agent_result_created(
        self,
        thread_id: str,
        agent_uid: str,
        success: bool = True
    ):
        """
        Assert agent result was created in workspace.
        
        Args:
            thread_id: Thread ID to check
            agent_uid: Agent UID that should have created result
            success: Expected success status
        """
        workspace = self.get_workspace(thread_id)
        assert workspace is not None, f"Workspace not found for thread {thread_id}"
        
        results = workspace.context.results
        agent_results = [r for r in results if r.agent_id == agent_uid]
        
        assert len(agent_results) > 0, \
            f"No results found from agent {agent_uid}"
        
        latest_result = agent_results[-1]
        assert latest_result.success == success, \
            f"Agent result success={latest_result.success}, expected={success}"
        
        return latest_result
