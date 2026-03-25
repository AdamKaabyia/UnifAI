"""
Factory for creating configured nodes for testing.

Provides factory methods to create nodes with common configurations,
reducing duplication and ensuring consistency across tests.
"""

from typing import List, Dict, Any, Optional, Type
from unittest.mock import Mock

from mas.elements.nodes.orchestrator.orchestrator_node import OrchestratorNode
from mas.elements.nodes.custom_agent.custom_agent import CustomAgentNode
from mas.elements.tools.common.base_tool import BaseTool
from mas.graph.state.state_view import StateView
from tests.base.test_helpers import create_test_step_context


class NodeFactory:
    """
    Factory for creating configured nodes for testing.
    
    Provides static methods to create nodes with common configurations,
    handling the boilerplate of state setup, context configuration, and
    adjacency management.
    """
    
    @staticmethod
    def create_orchestrator(
        llm=None,
        state: StateView = None,
        uid: str = "test_orchestrator",
        adjacent_nodes: List[str] = None,
        tools: List[BaseTool] = None,
        system_message: str = "",
        max_rounds: int = 20,
        **kwargs
    ) -> OrchestratorNode:
        """
        Create fully configured orchestrator for testing.
        
        Args:
            llm: LLM instance (creates mock if not provided)
            state: StateView instance (required for full functionality)
            uid: Unique identifier for the orchestrator
            adjacent_nodes: List of adjacent node UIDs
            tools: List of domain tools
            system_message: System message for orchestrator
            max_rounds: Maximum reasoning rounds
            **kwargs: Additional arguments for OrchestratorNode
            
        Returns:
            Configured OrchestratorNode instance
        """
        from tests.fixtures.common.llm_fixtures import create_mock_llm
        
        if llm is None:
            llm = create_mock_llm()
        
        if adjacent_nodes is None:
            adjacent_nodes = []
        
        if tools is None:
            tools = []
        
        # Create orchestrator
        orchestrator = OrchestratorNode(
            llm=llm,
            tools=tools,
            system_message=system_message,
            max_rounds=max_rounds,
            **kwargs
        )
        
        # Set up context
        step_context = create_test_step_context(uid, adjacent_nodes)
        orchestrator.set_context(step_context)
        
        # Set up state if provided
        if state:
            orchestrator._state = state
        
        return orchestrator
    
    @staticmethod
    def create_custom_agent(
        llm=None,
        state: StateView = None,
        uid: str = "test_agent",
        adjacent_nodes: List[str] = None,
        tools: List[BaseTool] = None,
        system_message: str = "",
        strategy_type: str = "react",
        max_rounds: int = 10,
        **kwargs
    ) -> CustomAgentNode:
        """
        Create fully configured custom agent for testing.
        
        Args:
            llm: LLM instance (creates mock if not provided)
            state: StateView instance (required for full functionality)
            uid: Unique identifier for the agent
            adjacent_nodes: List of adjacent node UIDs
            tools: List of tools for the agent
            system_message: System message for agent
            strategy_type: Strategy type (react, plan_execute, etc.)
            max_rounds: Maximum reasoning rounds
            **kwargs: Additional arguments for CustomAgentNode
            
        Returns:
            Configured CustomAgentNode instance
        """
        from tests.fixtures.common.llm_fixtures import create_mock_llm
        from tests.fixtures.common.tool_fixtures import create_basic_test_tools
        
        if llm is None:
            llm = create_mock_llm()
        
        if adjacent_nodes is None:
            adjacent_nodes = []
        
        if tools is None:
            tools = create_basic_test_tools()
        
        # Create agent
        agent = CustomAgentNode(
            llm=llm,
            tools=tools,
            system_message=system_message,
            strategy_type=strategy_type,
            max_rounds=max_rounds,
            **kwargs
        )
        
        # Set up context
        step_context = create_test_step_context(uid, adjacent_nodes)
        agent.set_context(step_context)
        
        # Set up state if provided
        if state:
            agent._state = state
        
        return agent
    
    @staticmethod
    def create_node_with_state(
        node_class: Type,
        state: StateView,
        uid: str,
        adjacent_nodes: List[str] = None,
        **node_kwargs
    ):
        """
        Generic factory method to create any node type with state.
        
        Args:
            node_class: The node class to instantiate
            state: StateView instance
            uid: Unique identifier for the node
            adjacent_nodes: List of adjacent node UIDs
            **node_kwargs: Additional arguments to pass to node constructor
            
        Returns:
            Configured node instance with state and context set up
        """
        if adjacent_nodes is None:
            adjacent_nodes = []
        
        # Create the node instance
        node = node_class(**node_kwargs)
        
        # Set up context with adjacency
        step_context = create_test_step_context(uid, adjacent_nodes)
        node.set_context(step_context)
        
        # Set up state
        node._state = state
        
        return node
    
    @staticmethod
    def create_orchestrator_with_workers(
        llm=None,
        state: StateView = None,
        orchestrator_uid: str = "test_orchestrator",
        worker_count: int = 2,
        worker_prefix: str = "worker",
        **kwargs
    ) -> tuple[OrchestratorNode, List[str]]:
        """
        Create orchestrator with configured worker nodes.
        
        Args:
            llm: LLM instance
            state: StateView instance
            orchestrator_uid: Orchestrator UID
            worker_count: Number of worker nodes
            worker_prefix: Prefix for worker UIDs
            **kwargs: Additional arguments for orchestrator
            
        Returns:
            Tuple of (orchestrator, list of worker UIDs)
        """
        worker_uids = [f"{worker_prefix}_{i}" for i in range(1, worker_count + 1)]
        
        orchestrator = NodeFactory.create_orchestrator(
            llm=llm,
            state=state,
            uid=orchestrator_uid,
            adjacent_nodes=worker_uids,
            **kwargs
        )
        
        return orchestrator, worker_uids
    
    @staticmethod
    def create_agent_cluster(
        count: int = 3,
        llm=None,
        state: StateView = None,
        agent_prefix: str = "agent",
        orchestrator_uid: str = "orchestrator",
        **kwargs
    ) -> List[CustomAgentNode]:
        """
        Create a cluster of agents that can communicate with an orchestrator.
        
        Args:
            count: Number of agents to create
            llm: LLM instance (shared across agents if provided)
            state: StateView instance
            agent_prefix: Prefix for agent UIDs
            orchestrator_uid: UID of orchestrator they connect to
            **kwargs: Additional arguments for agents
            
        Returns:
            List of configured CustomAgentNode instances
        """
        agents = []
        for i in range(1, count + 1):
            agent = NodeFactory.create_custom_agent(
                llm=llm,
                state=state,
                uid=f"{agent_prefix}_{i}",
                adjacent_nodes=[orchestrator_uid],
                **kwargs
            )
            agents.append(agent)
        
        return agents
